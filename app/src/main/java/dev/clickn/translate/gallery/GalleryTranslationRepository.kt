// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.R
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.data.TranslationPreset
import dev.clickn.translate.data.TranslationPresetCatalog
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import timber.log.Timber

internal fun galleryTaskMatchingPreset(settings: Settings): TranslationPreset? {
    val savedPresets = TranslationPresetCatalog.all(settings.translationPresets)
        .filterNot { it.id == TranslationPresetCatalog.UNSAVED_DRAFT_ID }
    val settingsHash = TranslationPresetCatalog.hashForSettings(settings)
    return savedPresets.firstOrNull {
        it.id == settings.activeTranslationPresetId &&
            TranslationPresetCatalog.matchesHash(it, settingsHash)
    } ?: savedPresets.firstOrNull {
        TranslationPresetCatalog.matchesHash(it, settingsHash)
    }
}

@Singleton
class GalleryTranslationRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dao: GalleryTranslationDao,
    private val settingsRepository: SettingsRepository,
    private val translatedPreviewStore: GalleryTranslatedPreviewStore,
    private val json: Json,
) {
    private val legacyResultRepair = GalleryLegacyResultRepair(dao, json) { translated, total ->
        AppLocalePrefs.live(context).getString(R.string.gallery_item_partial_error, translated, total)
    }

    private fun <T> afterInputCleanup(upstream: Flow<T>): Flow<T> = flow {
        GalleryPrivateInputAccess.prepare(context.filesDir.toPath(), dao::privateInputReferences)
        legacyResultRepair.run()
        emitAll(upstream)
    }.flowOn(Dispatchers.IO)

    fun observeTasks(): Flow<List<GalleryTranslationTaskEntity>> = afterInputCleanup(dao.observeTasks())

    fun observeLatestTask(): Flow<GalleryTranslationTaskEntity?> = afterInputCleanup(dao.observeLatestTask())

    fun observeFeaturedTask(): Flow<GalleryTranslationTaskEntity?> = afterInputCleanup(dao.observeFeaturedTask())

    fun observeTask(taskId: String): Flow<GalleryTranslationTaskEntity?> = afterInputCleanup(dao.observeTask(taskId))

    fun observeItems(taskId: String): Flow<List<GalleryTranslationItemEntity>> =
        afterInputCleanup(dao.observeItems(taskId))

    fun observeItem(itemId: String): Flow<GalleryTranslationItemEntity?> = afterInputCleanup(dao.observeItem(itemId))

    suspend fun getTask(taskId: String): GalleryTranslationTaskEntity? {
        GalleryPrivateInputAccess.prepare(context.filesDir.toPath(), dao::privateInputReferences)
        legacyResultRepair.run()
        return dao.getTask(taskId)
    }

    suspend fun getItems(taskId: String): List<GalleryTranslationItemEntity> {
        GalleryPrivateInputAccess.prepare(context.filesDir.toPath(), dao::privateInputReferences)
        legacyResultRepair.run()
        return dao.getItems(taskId)
    }

    suspend fun createTask(
        uriStrings: List<String>,
        settingsSnapshot: Settings? = null,
    ): GalleryPreparedTask {
        val taskId = UUID.randomUUID().toString()
        var enteredPublication = false
        return try {
            GalleryPrivateInputAccess.publication(context.filesDir.toPath(), dao::privateInputReferences) {
                enteredPublication = true
                createTask(taskId, uriStrings, settingsSnapshot)
            }
        } catch (error: Throwable) {
            // Also covers cancellation on the IO -> caller handoff after Room commits.
            // No worker is enqueued until this method has returned its prepared task.
            if (enteredPublication) withContext(NonCancellable + Dispatchers.IO) {
                GalleryPrivateInputAccess.rollback {
                    val removed = runCatching { dao.deleteTask(taskId) }
                        .onFailure { Timber.w(it, "Unable to roll back gallery task %s", taskId) }
                        .isSuccess
                    if (removed) {
                        runCatching { settingsRepository.forgetSnapshotCredentials("gallery_$taskId") }
                            .onFailure { Timber.w(it, "Unable to remove gallery snapshot %s", taskId) }
                        runCatching {
                            File(context.filesDir, "$TASK_FILES_DIR/$taskId").deleteRecursively()
                        }.onFailure { Timber.w(it, "Unable to remove gallery import files %s", taskId) }
                    }
                }
            }
            throw error
        }
    }

    private suspend fun createTask(
        taskId: String,
        uriStrings: List<String>,
        settingsSnapshot: Settings?,
    ): GalleryPreparedTask = withContext(Dispatchers.IO) {
        val selected = GalleryTranslationWorkPolicy.normalizeSelection(uriStrings)
        require(selected.isNotEmpty()) { "No images selected." }

        val now = System.currentTimeMillis()
        val settings = settingsSnapshot ?: settingsRepository.get()
        val activePreset = galleryTaskMatchingPreset(settings)
        val snapshot = TranslationPresetCatalog.fromSettings(
            id = "gallery_$taskId",
            name = activePreset?.name.orEmpty(),
            shortName = activePreset?.shortName.orEmpty(),
            settings = settings,
        )
        val items = selected.mapIndexed { index, uriString ->
            prepareItem(
                taskId = taskId,
                position = index,
                uriString = uriString,
                now = now,
            )
        }
        val failedCount = items.count { it.status == GalleryItemStatus.FAILED }
        val task = GalleryTranslationTaskEntity(
            id = taskId,
            createdAtMs = now,
            sourceLang = settings.sourceLang,
            targetLang = settings.targetLang,
            ocrEngine = settings.ocrEngine.name,
            translatorEngine = settings.translatorEngine.name,
            presetName = activePreset?.name.orEmpty(),
            settingsSnapshotJson = json.encodeToString(snapshot),
            totalCount = items.size,
            completedCount = failedCount,
            failedCount = failedCount,
            lastError = items.firstOrNull { it.status == GalleryItemStatus.FAILED }
                ?.errorMessage
                .orEmpty(),
        )
        currentCoroutineContext().ensureActive()
        settingsRepository.rememberSnapshotCredentials(snapshot, settings)
        dao.insertTaskWithItems(task, items)
        GalleryPreparedTask(
            id = taskId,
            sourceLang = settings.sourceLang,
            targetLang = settings.targetLang,
            ocrEngine = settings.ocrEngine,
            translatorEngine = settings.translatorEngine,
            imageCount = items.size,
        )
    }

    suspend fun settingsForTask(task: GalleryTranslationTaskEntity): Settings {
        // Decode and validate the persisted route before resolving any credentials.
        val snapshot = decodeGalleryTaskSnapshot(task, json)
        return settingsRepository.settingsForSnapshot(snapshot).copy(
            // Gallery work has no active foreground game. Global glossary entries remain
            // available, while app-specific memory must not attach to whichever app happens
            // to be visible when WorkManager starts.
            sendAppNameToTranslator = false,
            runtimeTranslationScopePackage = task.scopePackage,
            runtimeTranslationScopeLabel = task.scopeLabel,
        )
    }

    internal fun exportRenderModeForTask(task: GalleryTranslationTaskEntity): GalleryExportRenderMode =
        runCatching {
            val snapshot = json.decodeFromString<TranslationPreset>(task.settingsSnapshotJson)
            galleryExportRenderMode(snapshot.renderMode, snapshot.overlayStyleMode)
        }.getOrElse {
            Timber.w(it, "Gallery task %s has an invalid export render snapshot", task.id)
            GalleryExportRenderMode.FIXED_BLOCKS
        }

    suspend fun resetInterruptedItems(taskId: String) {
        dao.resetInterruptedItems(taskId, System.currentTimeMillis())
    }

    suspend fun markTaskRunning(taskId: String): Boolean =
        dao.markTaskRunning(taskId, GalleryTaskStatus.RUNNING, System.currentTimeMillis()) == 1

    suspend fun markTaskWaitingRetry(taskId: String, lastError: String) {
        dao.markTaskWaitingRetry(taskId, lastError)
    }

    suspend fun nextPendingItem(taskId: String): GalleryTranslationItemEntity? =
        dao.nextPendingItem(taskId)

    suspend fun markItemRunning(
        taskId: String,
        item: GalleryTranslationItemEntity,
    ): GalleryTranslationItemEntity? {
        require(item.taskId == taskId)
        return dao.claimItem(item, System.currentTimeMillis())
    }

    suspend fun completeItem(
        itemId: String,
        expectedVersion: Long,
        decoded: GalleryDecodedImage,
        processedWidth: Int,
        processedHeight: Int,
        segments: List<GalleryTranslationSegment>,
    ): GalleryTranslationItemEntity? {
        require(GallerySegmentRecovery.missingIndices(segments).isEmpty()) { "An incomplete image cannot be marked complete." }
        return persistItemResult(itemId, expectedVersion, decoded, processedWidth, processedHeight, segments,
            GalleryItemStatus.SUCCEEDED)
    }

    /** Remains RUNNING so interruption recovery can reclaim the saved recognition/results. */
    internal suspend fun checkpointIncompleteItem(
        itemId: String,
        expectedVersion: Long,
        decoded: GalleryDecodedImage,
        processedWidth: Int,
        processedHeight: Int,
        segments: List<GalleryTranslationSegment>,
    ): GalleryTranslationItemEntity? = persistItemResult(itemId, expectedVersion, decoded,
        processedWidth, processedHeight, segments, GalleryItemStatus.RUNNING)

    private suspend fun persistItemResult(
        itemId: String,
        expectedVersion: Long,
        decoded: GalleryDecodedImage,
        processedWidth: Int,
        processedHeight: Int,
        segments: List<GalleryTranslationSegment>,
        status: GalleryItemStatus,
    ): GalleryTranslationItemEntity? {
        val changed = dao.completeItem(
            itemId = itemId,
            expectedVersion = expectedVersion,
            originalWidth = decoded.originalWidth,
            originalHeight = decoded.originalHeight,
            processedWidth = processedWidth,
            processedHeight = processedHeight,
            sourceText = segments.joinToString("\n") { it.sourceText },
            translatedText = segments.filter { it.translatedText.isNotBlank() }.joinToString("\n") { it.translatedText },
            segmentsJson = json.encodeToString(segments),
            now = System.currentTimeMillis(),
            status = status,
        )
        return if (changed == 1) dao.getItem(itemId) else null
    }

    suspend fun markItemFailure(
        itemId: String,
        expectedVersion: Long,
        retry: Boolean,
        message: String,
    ): Boolean = dao.markItemFailed(
            itemId = itemId,
            expectedVersion = expectedVersion,
            status = if (retry) GalleryItemStatus.QUEUED else GalleryItemStatus.FAILED,
            message = message,
            now = System.currentTimeMillis(),
        ) == 1


    suspend fun refreshProgress(taskId: String, lastError: String = ""): GalleryTaskProgress {
        val row = dao.progress(taskId)
        val progress = GalleryTaskProgress(
            total = row.total,
            succeeded = row.succeeded,
            failed = row.failed,
            canceled = row.canceled,
            partial = row.partial,
        )
        dao.updateProgress(
            taskId = taskId,
            total = progress.total,
            completed = progress.completed,
            succeeded = progress.succeeded,
            failed = progress.failed,
            lastError = lastError,
        )
        return progress
    }

    suspend fun finishTask(taskId: String, lastError: String = ""): GalleryTaskStatus {
        val task = dao.getTask(taskId)
        val progress = refreshProgress(taskId, lastError)
        val status = GalleryTranslationWorkPolicy.terminalStatus(
            progress = progress,
            canceled = task?.status == GalleryTaskStatus.CANCELED,
        )
        val changed = dao.finishTask(
            taskId = taskId,
            status = status,
            finishedAtMs = System.currentTimeMillis(),
            lastError = lastError,
        )
        if (changed == 1) legacyResultRepair.repairTask(taskId)
        return dao.getTask(taskId)?.status ?: GalleryTaskStatus.CANCELED
    }

    suspend fun failTaskConfiguration(taskId: String, message: String) {
        dao.failPendingConfiguration(taskId, message, System.currentTimeMillis())
        finishTask(taskId, message)
    }

    suspend fun cancelTask(taskId: String) {
        dao.cancelTaskAndItems(taskId, System.currentTimeMillis())
        refreshProgress(taskId)
    }

    suspend fun failedRetrySelection(taskId: String): GalleryRetrySelection? = dao.failedRetrySelection(taskId)

    suspend fun resetSelectedFailures(taskId: String, selection: GalleryRetrySelection): Int =
        dao.resetSelectedFailures(taskId, selection, System.currentTimeMillis())

    suspend fun resetFailedTask(taskId: String): Int =
        dao.resetFailedTask(taskId, System.currentTimeMillis())

    suspend fun deleteTask(taskId: String) = withContext(Dispatchers.IO) {
        val items = dao.getItems(taskId)
        dao.deleteTask(taskId)
        // Once the durable task has gone, caller cancellation must not strand its private files.
        withContext(NonCancellable) {
            try {
                settingsRepository.forgetSnapshotCredentials("gallery_$taskId")
            } finally {
                try {
                    items.filter { it.localPath.isBlank() }.map(GalleryTranslationItemEntity::sourceUri)
                        .filter(String::isNotBlank)
                        .distinct()
                        .forEach { sourceUri ->
                            if (dao.countSourceUriReferences(sourceUri) == 0) {
                                runCatching {
                                    context.contentResolver.releasePersistableUriPermission(
                                        Uri.parse(sourceUri), Intent.FLAG_GRANT_READ_URI_PERMISSION,
                                    )
                                }
                            }
                        }
                } finally {
                    try {
                        File(context.filesDir, "$TASK_FILES_DIR/$taskId").deleteRecursively()
                    } finally {
                        translatedPreviewStore.deleteTask(taskId)
                    }
                }
            }
        }
    }

    private suspend fun prepareItem(
        taskId: String,
        position: Int,
        uriString: String,
        now: Long,
    ): GalleryTranslationItemEntity {
        val importContext = currentCoroutineContext()
        importContext.ensureActive()
        val uri = Uri.parse(uriString)
        val itemId = UUID.randomUUID().toString()
        val displayName = displayName(uri).ifBlank { "image_${position + 1}" }
        val hadPersistedGrant = runCatching {
            context.contentResolver.persistedUriPermissions.any { it.isReadPermission && it.uri == uri }
        }.getOrDefault(false)
        val persistable = hadPersistedGrant || persistReadPermission(uri)
        // Only a grant acquired for this copy may be released. Existing/legacy grants are borrowed.
        return try {
            importContext.ensureActive()
            var intendedLocalPath = ""
            runCatching {
                val targetDir = File(context.filesDir, "$TASK_FILES_DIR/$taskId/source").apply {
                    check(mkdirs() || isDirectory)
                }
                val extension = displayName.substringAfterLast('.', "")
                    .takeIf { it.matches(Regex("[A-Za-z0-9]{1,8}")) }
                    ?.let { ".$it" }
                    .orEmpty()
                val target = File(targetDir, "$itemId$extension")
                intendedLocalPath = target.absolutePath
                val copyBudget = galleryImageCopyBudget(persistable, targetDir.usableSpace)
                try {
                    context.contentResolver.openInputStream(uri).use { input ->
                        requireNotNull(input) { "Cannot open selected image." }
                        FileOutputStream(target).use { output ->
                            copyGalleryImage(input, output, maxBytes = copyBudget, checkpoint = {
                                importContext.ensureActive()
                                if (targetDir.usableSpace <= GALLERY_COPY_STORAGE_RESERVE) {
                                    throw java.io.IOException("Not enough free space to copy the selected image.")
                                }
                            })
                            output.fd.sync()
                        }
                    }
                    importContext.ensureActive()
                } catch (error: Exception) {
                    target.delete()
                    throw error
                }
                GalleryTranslationItemEntity(
                    id = itemId,
                    taskId = taskId,
                    position = position,
                    sourceUri = uriString,
                    localPath = target.absolutePath,
                    displayName = displayName,
                    updatedAtMs = now,
                )
            }.getOrElse { error ->
                if (error is CancellationException) throw error
                GalleryTranslationItemEntity(
                    id = itemId,
                    taskId = taskId,
                    position = position,
                    sourceUri = uriString,
                    localPath = intendedLocalPath.ifBlank {
                        File(context.filesDir, "$TASK_FILES_DIR/$taskId/source/$itemId.missing").absolutePath
                    },
                    displayName = displayName,
                    status = GalleryItemStatus.FAILED,
                    errorMessage = error.message ?: error.javaClass.simpleName,
                    updatedAtMs = now,
                )
            }
        } finally {
            if (persistable && !hadPersistedGrant) {
                withContext(NonCancellable + Dispatchers.IO) {
                    runCatching {
                        context.contentResolver.releasePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }.onFailure { Timber.w("Unable to release an owned temporary gallery read grant") }
                }
            }
        }
    }

    private fun persistReadPermission(uri: Uri): Boolean {
        if (uri.scheme == ContentResolver.SCHEME_FILE) return false
        return runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
            true
        }.getOrElse {
            Timber.i(it, "URI permission could not be persisted; applying the fallback copy budget")
            false
        }
    }

    private fun displayName(uri: Uri): String {
        if (uri.scheme == ContentResolver.SCHEME_FILE) {
            return uri.lastPathSegment.orEmpty()
        }
        return runCatching {
            context.contentResolver.query(
                uri,
                arrayOf(OpenableColumns.DISPLAY_NAME),
                null,
                null,
                null,
            )?.use { cursor ->
                if (!cursor.moveToFirst()) return@use ""
                val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (index >= 0) cursor.getString(index).orEmpty() else ""
            }.orEmpty()
        }.getOrDefault("")
    }

    private companion object {
        const val TASK_FILES_DIR = "gallery_translation"
    }
}
