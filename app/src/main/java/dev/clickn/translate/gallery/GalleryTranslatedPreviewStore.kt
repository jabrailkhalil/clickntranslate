// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.gallery

import android.content.Context
import android.graphics.Bitmap
import android.system.Os
import dev.clickn.translate.data.Settings
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import timber.log.Timber

@Singleton
class GalleryTranslatedPreviewStore @Inject constructor(
    @ApplicationContext context: Context,
    private val imageDecoder: GalleryImageDecoder,
    private val renderer: GalleryTranslatedImageRenderer,
    private val json: Json,
    private val dao: GalleryTranslationDao,
) {
    private val root = File(context.cacheDir, CACHE_ROOT)
    private val cacheDirectory = context.cacheDir
    private val generationMutex = GalleryTransientFiles.previewGenerationMutex

    suspend fun storeTranslatedPreview(
        item: GalleryTranslationItemEntity,
        source: Bitmap,
        processedWidth: Int,
        processedHeight: Int,
        segments: List<GalleryTranslationSegment>,
        settings: Settings,
    ): Boolean = safely(item, "store") {
        if (galleryExportRenderMode(settings) == GalleryExportRenderMode.UNSUPPORTED_FLOATING) {
            return@safely false
        }
        withContext(Dispatchers.IO) {
            generationMutex.withLock {
                GalleryTransientFiles.preparePreviews(cacheDirectory)
                writePreview(
                    item = item,
                    source = source,
                    processedWidth = processedWidth,
                    processedHeight = processedHeight,
                    segments = segments,
                    settings = settings,
                ) != null
            }
        }
    } ?: false

    suspend fun loadTranslatedThumbnail(
        item: GalleryTranslationItemEntity,
        settings: Settings,
    ): Bitmap? = loadTranslated(item, settings, thumbnail = true)

    suspend fun loadTranslatedPreview(
        item: GalleryTranslationItemEntity,
        settings: Settings,
    ): Bitmap? = loadTranslated(item, settings, thumbnail = false)

    suspend fun deleteTask(taskId: String) = withContext(Dispatchers.IO) {
        generationMutex.withLock { File(root, taskId).deleteRecursively() }
        Unit
    }

    private suspend fun loadTranslated(
        item: GalleryTranslationItemEntity,
        settings: Settings,
        thumbnail: Boolean,
    ): Bitmap? = safely(item, if (thumbnail) "thumbnail" else "preview") {
        if (
            !galleryResultUsesTranslatedPreview(
                status = item.status,
                renderMode = galleryExportRenderMode(settings),
                hasTranslatedText = item.translatedText.isNotBlank(),
            )
        ) {
            return@safely null
        }
        val previewFile = withContext(Dispatchers.IO) {
            ensurePreview(item, settings)
        } ?: return@safely null
        loadGalleryBitmap {
            if (thumbnail) {
                imageDecoder.decodeThumbnail(
                    sourceUri = "",
                    localPath = previewFile.absolutePath,
                )
            } else {
                imageDecoder.decodePreview(
                    sourceUri = "",
                    localPath = previewFile.absolutePath,
                )
            }
        }
    }

    private suspend fun ensurePreview(
        item: GalleryTranslationItemEntity,
        settings: Settings,
    ): File? = generationMutex.withLock {
        GalleryTransientFiles.preparePreviews(cacheDirectory)
        if (!isCommitted(item)) return@withLock null
        GalleryTransientFiles.previewTaskDirectory(cacheDirectory, item.taskId)
        val target = previewFile(item)
        if (Files.isRegularFile(target.toPath(), NOFOLLOW_LINKS) && target.length() > 0L) return@withLock target

        val segments = json.decodeFromString<List<GalleryTranslationSegment>>(item.segmentsJson)
            .filter { it.translatedText.isNotBlank() }
        if (segments.isEmpty()) return@withLock null

        var decoded: GalleryDecodedImage? = null
        try {
            val decodeContext = currentCoroutineContext()
            decoded = imageDecoder.decode(item, checkpoint = { decodeContext.ensureActive() })
            writePreview(
                item = item,
                source = decoded.bitmap,
                processedWidth = item.processedWidth,
                processedHeight = item.processedHeight,
                segments = segments,
                settings = settings,
            )
        } finally {
            decoded?.bitmap?.takeIf { !it.isRecycled }?.recycle()
        }
    }

    private suspend fun writePreview(
        item: GalleryTranslationItemEntity,
        source: Bitmap,
        processedWidth: Int,
        processedHeight: Int,
        segments: List<GalleryTranslationSegment>,
        settings: Settings,
    ): File? {
        val generationContext = currentCoroutineContext()
        generationContext.ensureActive()
        if (!isCommitted(item)) return null
        val target = previewFile(item)
        val directory = GalleryTransientFiles.previewTaskDirectory(cacheDirectory, item.taskId)
        val temporary = File.createTempFile("${item.id}-", ".tmp", directory)
        var rendered: Bitmap? = null
        try {
            val outputBitmap = renderer.render(
                source = source,
                processedWidth = processedWidth,
                processedHeight = processedHeight,
                segments = segments,
                settings = settings,
            )
            rendered = outputBitmap
            generationContext.ensureActive()
            FileOutputStream(temporary).use { output ->
                check(outputBitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)) {
                    "Unable to encode translated preview."
                }
            }
            generationContext.ensureActive()
            if (!isCommitted(item)) return null
            Os.rename(temporary.absolutePath, target.absolutePath)
            return target
        } finally {
            temporary.delete()
            rendered
                ?.takeIf { it !== source && !it.isRecycled }
                ?.recycle()
        }
    }

    private fun previewFile(item: GalleryTranslationItemEntity): File =
        File(File(root, item.taskId), "${item.id}-${item.updatedAtMs}-v2.jpg")

    private suspend fun isCommitted(item: GalleryTranslationItemEntity): Boolean {
        val stored = dao.getItem(item.id) ?: return false
        return stored.taskId == item.taskId && stored.status == item.status &&
            (stored.status == GalleryItemStatus.SUCCEEDED ||
                (stored.status == GalleryItemStatus.FAILED && stored.translatedText.isNotBlank())) &&
            stored.updatedAtMs == item.updatedAtMs
    }

    private suspend fun <T> safely(
        item: GalleryTranslationItemEntity,
        operation: String,
        block: suspend () -> T,
    ): T? = try {
        block()
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (error: Throwable) {
        Timber.w(
            error,
            "Gallery translated preview %s failed task=%s item=%s",
            operation,
            item.taskId,
            item.id,
        )
        null
    }

    private companion object {
        const val CACHE_ROOT = GalleryTransientFiles.PREVIEW_ROOT
        const val JPEG_QUALITY = 90
    }
}

internal fun galleryResultUsesTranslatedPreview(
    status: GalleryItemStatus,
    renderMode: GalleryExportRenderMode,
    hasTranslatedText: Boolean = false,
): Boolean = (status == GalleryItemStatus.SUCCEEDED || (status == GalleryItemStatus.FAILED && hasTranslatedText)) &&
    renderMode != GalleryExportRenderMode.UNSUPPORTED_FLOATING
