// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.Rect
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import dev.clickn.translate.R
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.needsRawBitmap
import dev.clickn.translate.ocr.BitmapPreprocessor
import dev.clickn.translate.ocr.RoutingOcrEngine
import dev.clickn.translate.ocr.TextBlock
import dev.clickn.translate.ocr.TextOrientation
import dev.clickn.translate.ocr.TextRegionGranularity
import dev.clickn.translate.translate.RoutingTranslator
import dev.clickn.translate.translate.TranslationVisualContextPreparer
import dev.clickn.translate.translate.TranslationVisualDebugStore
import dev.clickn.translate.ui.MainActivity
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import timber.log.Timber
import kotlinx.serialization.json.Json
import kotlin.math.ceil
import kotlin.math.floor

@HiltWorker
class GalleryTranslationWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val repository: GalleryTranslationRepository,
    private val imageDecoder: GalleryImageDecoder,
    private val ocrEngine: RoutingOcrEngine,
    private val translator: RoutingTranslator,
    private val translatedPreviewStore: GalleryTranslatedPreviewStore,
    private val json: Json,
) : CoroutineWorker(appContext, workerParams) {

    private val translationVisualDebugStore by lazy {
        TranslationVisualDebugStore.forContext(applicationContext)
    }

    override suspend fun doWork(): Result {
        val taskId = inputData.getString(KEY_TASK_ID).orEmpty()
        if (taskId.isBlank()) return Result.failure()
        val retryIds = inputData.getStringArray(KEY_RETRY_ITEM_IDS).orEmpty()
        val retryVersions = inputData.getLongArray(KEY_RETRY_ITEM_VERSIONS) ?: LongArray(0)
        if (retryIds.size != retryVersions.size || retryIds.size > GalleryTranslationWorkPolicy.MAX_IMAGES_PER_TASK ||
            retryIds.toSet().size != retryIds.size
        ) return Result.failure()
        if (retryIds.isNotEmpty()) {
            val expectedStatus = GalleryTaskStatus.entries.firstOrNull {
                it.name == inputData.getString(KEY_RETRY_TASK_STATUS)
            } ?: return Result.failure()
            if (expectedStatus !in setOf(GalleryTaskStatus.FAILED, GalleryTaskStatus.PARTIAL, GalleryTaskStatus.CANCELED)) {
                return Result.failure()
            }
            repository.resetSelectedFailures(taskId, GalleryRetrySelection(
                taskStatus = expectedStatus,
                finishedAtMs = inputData.getLong(KEY_RETRY_TASK_FINISHED_AT, 0L),
                items = retryIds.indices.map { GalleryRetryItem(retryIds[it], retryVersions[it]) },
            ))
        }
        val task = repository.getTask(taskId) ?: return Result.failure()
        if (task.status == GalleryTaskStatus.CANCELED) return Result.success()

        val settings = try {
            repository.settingsForTask(task)
        } catch (invalid: GalleryTaskSnapshotException) {
            repository.failTaskConfiguration(taskId, requireNotNull(invalid.message))
            return Result.failure()
        }
        val useForeground = GalleryTranslationWorkPolicy.shouldUseForeground(
            imageCount = task.totalCount,
            translatorEngine = settings.translatorEngine,
        )
        if (useForeground) {
            setForeground(createForegroundInfo(task, task.completedCount))
        }

        repository.resetInterruptedItems(taskId)
        if (!repository.markTaskRunning(taskId)) return Result.success()
        Timber.i("Gallery translation started task=%s images=%d", taskId, task.totalCount)

        while (true) {
            currentCoroutineContext().ensureActive()
            val latestTask = repository.getTask(taskId) ?: return Result.failure()
            if (latestTask.status == GalleryTaskStatus.CANCELED) return Result.success()
            val pending = repository.nextPendingItem(taskId) ?: break
            val item = repository.markItemRunning(taskId, pending) ?: continue

            try {
                processItem(item, settings)
                val progress = repository.refreshProgress(taskId)
                if (useForeground) {
                    setForeground(createForegroundInfo(latestTask, progress.completed))
                }
            } catch (cancellation: CancellationException) {
                throw cancellation
            } catch (error: Throwable) {
                val message = error.message?.take(500) ?: error.javaClass.simpleName
                val nextAttemptCount = item.attemptCount
                val retry = if (
                    error is IncompleteTranslationException ||
                    error is TranslationRequestException
                ) {
                    GalleryTranslationWorkPolicy.shouldRetryFailedTranslation(
                        enabled = settings.retryFailedTranslation &&
                            !translator.handlesTranslationFailureRetry(settings),
                        attemptCount = nextAttemptCount,
                    )
                } else {
                    GalleryTranslationWorkPolicy.shouldRetry(error, nextAttemptCount)
                }
                Timber.w(
                    error,
                    "Gallery translation item failed task=%s item=%s retry=%s attempt=%d",
                    taskId,
                    item.id,
                    retry,
                    nextAttemptCount,
                )
                val failedVersion = (error as? IncompleteTranslationException)?.resultVersion ?: item.updatedAtMs
                if (!repository.markItemFailure(item.id, failedVersion, retry, message)) continue
                repository.refreshProgress(taskId, message)
                if (retry) {
                    repository.markTaskWaitingRetry(taskId, message)
                    return Result.retry()
                }
            }
        }

        currentCoroutineContext().ensureActive()
        val status = repository.finishTask(taskId)
        Timber.i("Gallery translation finished task=%s status=%s", taskId, status)
        return Result.success()
    }

    private suspend fun processItem(
        item: GalleryTranslationItemEntity,
        settings: Settings,
    ) {
        val workContext = currentCoroutineContext()
        var decoded: GalleryDecodedImage? = null
        var preprocessed: Bitmap? = null
        try {
            decoded = imageDecoder.decode(item, checkpoint = { workContext.ensureActive() })
            workContext.ensureActive()
            val saved = GallerySegmentRecovery.resume(item, decoded.bitmap.width, decoded.bitmap.height, json)
            val segments = if (translator.isEndToEndFor(settings)) {
                if (saved != null && GallerySegmentRecovery.missingIndices(saved).isEmpty()) saved else {
                    val fresh = translateOrThrow {
                        translator.ocrAndTranslate(decoded.bitmap, settings)
                    }.map { (block, text) -> GalleryTranslationSegment.from(block, text) }
                    GallerySegmentRecovery.mergeImageOnlyResult(saved, fresh)
                }
            } else {
                val preprocessOptions = if (settings.ocrEngine.needsRawBitmap) {
                    settings.preprocess.copy(invert = false, binarize = false)
                } else {
                    settings.preprocess
                }
                val blocks = saved?.map(::restoreGalleryTextBlock) ?: run {
                    val ocrInput = BitmapPreprocessor.apply(decoded.bitmap, preprocessOptions)
                    preprocessed = ocrInput
                    val rawBlocks = try {
                        ocrEngine.recognizeWithSettings(bitmap = ocrInput, kind = settings.ocrEngine, settings = settings)
                    } finally {
                        if (ocrInput !== decoded.bitmap && !ocrInput.isRecycled) ocrInput.recycle()
                        preprocessed = null
                    }
                    workContext.ensureActive()
                    if (preprocessOptions.upscale2x) rawBlocks.map(::downscaleGalleryOcrBlock) else rawBlocks
                }
                if (blocks.isEmpty()) throw NoTextDetectedException()
                val visualPreparation = withContext(Dispatchers.Default) {
                    TranslationVisualContextPreparer.prepare(
                        bitmap = decoded.bitmap,
                        blocks = blocks,
                        settings = settings,
                        presentation = RenderMode.BLOCKS,
                        combineIntoSingleOutput = false,
                        origin = "gallery-${item.id}",
                        debugStore = translationVisualDebugStore,
                    )
                }
                visualPreparation.context?.let { visual ->
                    Timber.i(
                        "Gallery visual context item=%s image=%dx%d bytes=%d sha256=%s debugPath=%s",
                        item.id,
                        visual.width,
                        visual.height,
                        visual.byteCount,
                        visual.sha256,
                        visualPreparation.debugArtifact?.absolutePath ?: "none",
                    )
                }
                GallerySegmentRecovery.translateMissing(saved ?: blocks.map { GalleryTranslationSegment.from(it, null) }) { pending ->
                    translateOrThrow { translator.translateBatch(pending, visualPreparation.settings) }
                }
            }
            if (segments.isEmpty() || segments.all { it.sourceText.isBlank() && it.translatedText.isBlank() }) throw NoTextDetectedException()
            val missing = GallerySegmentRecovery.missingIndices(segments)
            if (missing.isNotEmpty()) {
                workContext.ensureActive()
                val progress = repository.checkpointIncompleteItem(item.id, item.updatedAtMs, decoded,
                    decoded.bitmap.width, decoded.bitmap.height, segments) ?: return
                val total = segments.count { it.sourceText.isNotBlank() }
                throw IncompleteTranslationException(progress.updatedAtMs,
                    AppLocalePrefs.live(applicationContext).getString(R.string.gallery_item_partial_error,
                        total - missing.size, total))
            }
            workContext.ensureActive()
            val completed = repository.completeItem(
                itemId = item.id,
                expectedVersion = item.updatedAtMs,
                decoded = decoded,
                processedWidth = decoded.bitmap.width,
                processedHeight = decoded.bitmap.height,
                segments = segments,
            ) ?: return
            // A cancelled/replaced claim cannot warm a cache for a result it did not commit.
            workContext.ensureActive()
            translatedPreviewStore.storeTranslatedPreview(
                item = completed,
                source = decoded.bitmap,
                processedWidth = decoded.bitmap.width,
                processedHeight = decoded.bitmap.height,
                segments = segments,
                settings = settings,
            )
        } finally {
            preprocessed?.takeIf { it !== decoded?.bitmap && !it.isRecycled }?.recycle()
            decoded?.bitmap?.takeIf { !it.isRecycled }?.recycle()
        }
    }

    private suspend fun <T> translateOrThrow(block: suspend () -> T): T = try {
        block()
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: Throwable) {
        throw TranslationRequestException(error)
    }

    private fun createForegroundInfo(
        task: GalleryTranslationTaskEntity,
        completed: Int,
    ): ForegroundInfo {
        val manager = applicationContext.getSystemService(NotificationManager::class.java)
        if (manager.getNotificationChannel(NOTIFICATION_CHANNEL_ID) == null) {
            manager.createNotificationChannel(
                NotificationChannel(
                    NOTIFICATION_CHANNEL_ID,
                    applicationContext.getString(R.string.gallery_notification_channel),
                    NotificationManager.IMPORTANCE_LOW,
                )
            )
        }
        val openTasks = PendingIntent.getActivity(
            applicationContext,
            task.id.hashCode(),
            Intent(applicationContext, MainActivity::class.java).apply {
                putExtra(MainActivity.EXTRA_START_ROUTE, ROUTE_GALLERY_TASKS)
                addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val progressText = applicationContext.getString(
            R.string.gallery_notification_progress,
            completed,
            task.totalCount,
        )
        val notification = NotificationCompat.Builder(applicationContext, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_gallery)
            .setContentTitle(applicationContext.getString(R.string.gallery_notification_title))
            .setContentText(progressText)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setContentIntent(openTasks)
            .setProgress(task.totalCount, completed, false)
            .build()
        val notificationId = NOTIFICATION_ID_BASE + (task.id.hashCode() and 0x0FFF)
        return if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
            ForegroundInfo(
                notificationId,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            ForegroundInfo(notificationId, notification)
        }
    }

    private class NoTextDetectedException : IllegalStateException("No text detected.")
    private class IncompleteTranslationException(val resultVersion: Long, message: String) : IllegalStateException(message)
    private class TranslationRequestException(cause: Throwable) :
        IllegalStateException(cause.message ?: cause.javaClass.simpleName, cause)

    companion object {
        const val KEY_TASK_ID = "task_id"
        const val KEY_RETRY_ITEM_IDS = "retry_item_ids"
        const val KEY_RETRY_ITEM_VERSIONS = "retry_item_versions"
        const val KEY_RETRY_TASK_STATUS = "retry_task_status"
        const val KEY_RETRY_TASK_FINISHED_AT = "retry_task_finished_at"
        const val ROUTE_GALLERY_TASKS = "GalleryTasks"
        private const val NOTIFICATION_CHANNEL_ID = "gallery_translation"
        private const val NOTIFICATION_ID_BASE = 6100
    }
}

internal fun restoreGalleryTextBlock(segment: GalleryTranslationSegment): TextBlock = TextBlock(
    text = segment.sourceText,
    boundingBox = segment.boundingBox.toAndroidRect(),
    sourceBoxes = segment.sourceBoxes.map(GalleryRect::toAndroidRect),
    confidence = segment.confidence,
    recognizedLanguage = segment.recognizedLanguage,
    layoutOrientation = segment.layoutOrientation?.let { value -> TextOrientation.entries.firstOrNull { it.name == value } },
    bubbleGroupId = segment.bubbleGroupId,
    regionId = segment.regionId,
    parentRegionId = segment.parentRegionId,
    regionGranularity = TextRegionGranularity.entries.firstOrNull { it.name == segment.regionGranularity }
        ?: TextRegionGranularity.UNKNOWN,
    presentationRotationDegrees = segment.presentationRotationDegrees,
)

internal fun downscaleGalleryOcrBlock(block: TextBlock): TextBlock {
    fun Rect.half(): Rect = Rect(
        floor(left / 2.0).toInt(), floor(top / 2.0).toInt(),
        ceil(right / 2.0).toInt(), ceil(bottom / 2.0).toInt(),
    )
    return block.copy(
        boundingBox = block.boundingBox.half(),
        sourceBoxes = block.sourceBoxes.map { it.half() },
    )
}
