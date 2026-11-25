package dev.clickn.translate.gallery

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Rect
import dev.clickn.translate.ocr.TextBlock
import androidx.exifinterface.media.ExifInterface
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslationPresetCatalog
import dev.clickn.translate.data.TranslatorEngine
import java.io.File
import java.util.UUID
import kotlin.math.abs
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Actual isolated Room/BitmapFactory/EXIF coverage; does not use app history, keys or cloud APIs. */
@RunWith(AndroidJUnit4::class)
class GalleryBackendIntegrationTest {
    private val context: Context = InstrumentationRegistry.getInstrumentation().targetContext
    private val json = Json { encodeDefaults = true; ignoreUnknownKeys = true }

    @Test fun cancelledTaskRejectsLateClaimCompletionFailureAndFinalization() = runBlocking {
        withRoom { dao ->
            val originals = seed(dao, "cancel", 3)
            assertEquals(1, dao.markTaskRunning("cancel", GalleryTaskStatus.RUNNING, 10))
            val claim = requireNotNull(dao.claimItem(originals[0], 10))
            val release = CompletableDeferred<Unit>()
            val late = async(Dispatchers.IO) { release.await(); complete(dao, claim, "late") }
            dao.cancelTaskAndItems("cancel", 10)
            release.complete(Unit)
            assertEquals(0, late.await())
            assertEquals(0, dao.markItemFailed(claim.id, claim.updatedAtMs, GalleryItemStatus.QUEUED, "late", 10))
            assertNull(dao.claimItem(requireNotNull(dao.getItem(originals[1].id)), 10))
            assertEquals(0, dao.markTaskRunning("cancel", GalleryTaskStatus.RUNNING, 10))
            assertEquals(0, dao.finishTask("cancel", GalleryTaskStatus.SUCCEEDED, 10, "late"))
            dao.resetInterruptedItems("cancel", 10)
            assertEquals(GalleryTaskStatus.CANCELED, dao.getTask("cancel")?.status)
            assertTrue(dao.getItems("cancel").all { it.status == GalleryItemStatus.CANCELED })
            assertTrue(dao.getItems("cancel").all { it.segmentsJson == "[]" && it.translatedText.isEmpty() })
        }
    }

    @Test fun restartAndExplicitRetryNeverReuseAnOldClaimEvenAtTheSameClockTick() = runBlocking {
        withRoom { dao ->
            val item = seed(dao, "restart", 1).single()
            val old = requireNotNull(dao.claimItem(item, 10))
            dao.resetInterruptedItems("restart", 10)
            val resumed = requireNotNull(dao.claimItem(requireNotNull(dao.getItem(item.id)), 10))
            assertTrue(resumed.updatedAtMs > old.updatedAtMs)
            assertEquals(0, complete(dao, old, "old"))
            assertEquals(0, dao.markItemFailed(old.id, old.updatedAtMs, GalleryItemStatus.FAILED, "old", 10))
            assertEquals(1, dao.markItemFailed(resumed.id, resumed.updatedAtMs, GalleryItemStatus.FAILED, "retry", 10))
            assertEquals(1, dao.resetFailedTask("restart", 10))
            val retried = requireNotNull(dao.claimItem(requireNotNull(dao.getItem(item.id)), 10))
            assertEquals(1, retried.attemptCount)
            assertTrue(retried.updatedAtMs > resumed.updatedAtMs)
            assertEquals(0, complete(dao, resumed, "stale after manual retry"))
            assertEquals(1, complete(dao, retried, "accepted"))
            assertEquals("accepted", dao.getItem(item.id)?.translatedText)
            assertEquals(GalleryItemStatus.SUCCEEDED, dao.getItem(item.id)?.status)
        }
    }

    @Test fun configurationFailureKeepsCompletedResultsAndCannotUndoCancellation() = runBlocking {
        withRoom { dao ->
            val items = seed(dao, "config", 3)
            val accepted = requireNotNull(dao.claimItem(items[0], 10))
            assertEquals(1, complete(dao, accepted, "keep"))
            dao.failPendingConfiguration("config", "invalid snapshot", 10)
            val progress = dao.progress("config")
            assertEquals(1, progress.succeeded)
            assertEquals(2, progress.failed)
            assertEquals("keep", dao.getItem(items[0].id)?.translatedText)
            assertEquals(GalleryTaskStatus.PARTIAL, GalleryTranslationWorkPolicy.terminalStatus(
                GalleryTaskProgress(progress.total, progress.succeeded, progress.failed), canceled = false,
            ))
            seed(dao, "cancel-config", 2)
            dao.cancelTaskAndItems("cancel-config", 10)
            dao.failPendingConfiguration("cancel-config", "late invalid snapshot", 10)
            assertTrue(dao.getItems("cancel-config").all { it.status == GalleryItemStatus.CANCELED })
        }
    }

    @Test fun durableRetryReceiptIsOneUseAndDoesNotResetAFailureFromItsNewAttempt() = runBlocking {
        withRoom { dao ->
            val item = seed(dao, "receipt", 1).single()
            val first = requireNotNull(dao.claimItem(item, 10))
            assertEquals(1, dao.markItemFailed(item.id, first.updatedAtMs, GalleryItemStatus.FAILED, "first", 10))
            assertEquals(1, dao.finishTask("receipt", GalleryTaskStatus.FAILED, 10, "first"))
            val request = requireNotNull(dao.failedRetrySelection("receipt"))
            assertEquals(1, dao.resetSelectedFailures("receipt", request, 10))
            val second = requireNotNull(dao.claimItem(requireNotNull(dao.getItem(item.id)), 10))
            assertEquals(1, second.attemptCount)
            assertEquals(1, dao.markItemFailed(item.id, second.updatedAtMs, GalleryItemStatus.FAILED, "second", 10))
            assertEquals(1, dao.finishTask("receipt", GalleryTaskStatus.FAILED, 10, "second"))
            assertEquals(0, dao.resetSelectedFailures("receipt", request, 10))
            val stored = requireNotNull(dao.getItem(item.id))
            assertEquals(GalleryItemStatus.FAILED, stored.status)
            assertEquals("second", stored.errorMessage)
            assertEquals(GalleryTaskStatus.FAILED, dao.getTask("receipt")?.status)
            assertEquals(1, dao.resetSelectedFailures("receipt", requireNotNull(dao.failedRetrySelection("receipt")), 10))
        }
    }

    @Test fun subsequentCancelRejectsQueuedRetryAndRetryNeverProcessesCanceledRemainder() = runBlocking {
        withRoom { dao ->
            val items = seed(dao, "cancel-retry", 3)
            val successful = requireNotNull(dao.claimItem(items[0], 10))
            assertEquals(1, complete(dao, successful, "keep"))
            val failed = requireNotNull(dao.claimItem(items[1], 10))
            assertEquals(1, dao.markItemFailed(failed.id, failed.updatedAtMs, GalleryItemStatus.FAILED, "first", 10))
            dao.cancelTaskAndItems("cancel-retry", 10)
            val staleRequest = requireNotNull(dao.failedRetrySelection("cancel-retry"))
            dao.cancelTaskAndItems("cancel-retry", 10) // Even the same clock tick changes the cancellation receipt.
            assertEquals(0, dao.resetSelectedFailures("cancel-retry", staleRequest, 10))
            assertEquals(GalleryTaskStatus.CANCELED, dao.getTask("cancel-retry")?.status)
            val explicitRequest = requireNotNull(dao.failedRetrySelection("cancel-retry"))
            assertEquals(listOf(failed.id), explicitRequest.items.map { it.id })
            assertEquals(1, dao.resetSelectedFailures("cancel-retry", explicitRequest, 10))
            val retry = requireNotNull(dao.claimItem(requireNotNull(dao.getItem(failed.id)), 10))
            assertEquals(1, complete(dao, retry, "retried"))
            assertNull(dao.nextPendingItem("cancel-retry"))
            val progress = dao.progress("cancel-retry")
            assertEquals(1, progress.canceled)
            assertEquals(2, progress.succeeded)
            val summary = GalleryTaskProgress(progress.total, progress.succeeded, progress.failed, progress.canceled)
            assertEquals(2, summary.completed)
            assertEquals(GalleryTaskStatus.PARTIAL, GalleryTranslationWorkPolicy.terminalStatus(summary, false))
            assertEquals("keep", dao.getItem(successful.id)?.translatedText)
            assertEquals(GalleryItemStatus.CANCELED, dao.getItem(items[2].id)?.status)
        }
    }

    @Test fun savedRouteAndClaimVersionSurviveClosingAndReopeningActualRoom() = runBlocking {
        val name = "gallery-owned-${UUID.randomUUID()}.db"
        var database: GalleryTranslationDatabase? = null
        try {
            database = Room.databaseBuilder(context, GalleryTranslationDatabase::class.java, name).build()
            val first = database.galleryTranslationDao()
            val original = seed(first, "persist", 1).single()
            val claimed = requireNotNull(first.claimItem(original, 10))
            val saved = requireNotNull(first.getTask("persist"))
            database.close()
            database = Room.databaseBuilder(context, GalleryTranslationDatabase::class.java, name).build()
            val reopened = database.galleryTranslationDao()
            val task = requireNotNull(reopened.getTask("persist"))
            assertEquals(saved.settingsSnapshotJson, task.settingsSnapshotJson)
            val preset = decodeGalleryTaskSnapshot(task, json)
            assertEquals(TranslatorEngine.GOOGLE, preset.translatorEngine)
            assertEquals("ar", preset.sourceLang)
            assertEquals("en", preset.targetLang)
            reopened.resetInterruptedItems("persist", 10)
            val fresh = requireNotNull(reopened.claimItem(requireNotNull(reopened.getItem(original.id)), 10))
            assertTrue(fresh.updatedAtMs > claimed.updatedAtMs)
            assertEquals(0, complete(reopened, claimed, "old process"))
            assertEquals(1, complete(reopened, fresh, "new process"))
        } finally {
            database?.close()
            context.deleteDatabase(name)
        }
    }

    @Test fun allEightExifOrientationsMatchAnIndependentCornerOracle() {
        withOwnedImages { directory ->
            val decoder = GalleryImageDecoder(context)
            val expected = listOf(
                listOf(Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW),
                listOf(Color.GREEN, Color.RED, Color.YELLOW, Color.BLUE),
                listOf(Color.YELLOW, Color.BLUE, Color.GREEN, Color.RED),
                listOf(Color.BLUE, Color.YELLOW, Color.RED, Color.GREEN),
                listOf(Color.RED, Color.BLUE, Color.GREEN, Color.YELLOW),
                listOf(Color.BLUE, Color.RED, Color.YELLOW, Color.GREEN),
                listOf(Color.YELLOW, Color.GREEN, Color.BLUE, Color.RED),
                listOf(Color.GREEN, Color.YELLOW, Color.RED, Color.BLUE),
            )
            for (orientation in 1..8) {
                val file = cornerJpeg(directory, orientation, 80, 48)
                val decoded = decoder.decode(imageItem(file))
                try {
                    val swapped = orientation >= 5
                    assertEquals(if (swapped) 48 else 80, decoded.originalWidth)
                    assertEquals(if (swapped) 80 else 48, decoded.originalHeight)
                    assertEquals(decoded.originalWidth, decoded.bitmap.width)
                    assertEquals(decoded.originalHeight, decoded.bitmap.height)
                    val colors = corners(decoded.bitmap)
                    expected[orientation - 1].zip(colors).forEachIndexed { index, (wanted, actual) ->
                        assertColor("EXIF=$orientation corner=$index", wanted, actual)
                    }
                } finally {
                    decoded.bitmap.recycle()
                }
            }
        }
    }

    @Test fun largeMirroredImageHasBoundedDecodedAllocationAndOrientedDimensions() {
        withOwnedImages { directory ->
            val decoder = GalleryImageDecoder(context)
            val file = cornerJpeg(directory, ExifInterface.ORIENTATION_TRANSVERSE, 4000, 2400)
            val decoded = decoder.decode(imageItem(file), maxDimension = 257)
            try {
                assertEquals(2400, decoded.originalWidth)
                assertEquals(4000, decoded.originalHeight)
                assertTrue(decoded.bitmap.width in 1..257)
                assertTrue(decoded.bitmap.height in 1..257)
                assertTrue(decoded.bitmap.allocationByteCount <= 257 * 257 * 4)
                listOf(Color.YELLOW, Color.GREEN, Color.BLUE, Color.RED).zip(corners(decoded.bitmap))
                    .forEachIndexed { index, (wanted, actual) -> assertColor("sampled EXIF7 corner=$index", wanted, actual) }
            } finally {
                decoded.bitmap.recycle()
            }
        }
    }

    @Test fun redecodingForExportPreservesEveryExifOrientationAndScaledCoordinates() {
        withOwnedImages { directory ->
            val decoder = GalleryImageDecoder(context)
            for (orientation in 1..8) {
                val item = imageItem(cornerJpeg(directory, orientation, 80, 48))
                val processed = decoder.decode(item, maxDimension = 20)
                try {
                    val exported = decoder.decode(item, maxDimension = 160)
                    try {
                        assertEquals(processed.bitmap.width * 4, exported.bitmap.width)
                        assertEquals(processed.bitmap.height * 4, exported.bitmap.height)
                        corners(processed.bitmap).zip(corners(exported.bitmap)).forEachIndexed { index, (a, b) ->
                            assertColor("export EXIF=$orientation corner=$index", a, b)
                        }
                        assertEquals(GalleryRect(4, 8, exported.bitmap.width - 4, exported.bitmap.height - 8),
                            scaledGalleryRect(
                                GalleryRect(1, 2, processed.bitmap.width - 1, processed.bitmap.height - 2),
                                processed.bitmap.width, processed.bitmap.height, exported.bitmap.width, exported.bitmap.height,
                            ))
                    } finally { exported.bitmap.recycle() }
                } finally { processed.bitmap.recycle() }
            }
        }
    }

    @Test fun upscaleMappingRetainsThinAndOddOcrBoxesIncludingSourceEraseGeometry() {
        val thin = Rect(2, 2, 3, 3)
        val crossing = Rect(-1, -3, 1, 3)
        val original = TextBlock("owned", thin, 1f, sourceBoxes = listOf(thin, crossing))
        val mapped = downscaleGalleryOcrBlock(original)
        assertEquals(Rect(1, 1, 2, 2), mapped.boundingBox)
        assertEquals(listOf(Rect(1, 1, 2, 2), Rect(-1, -2, 1, 2)), mapped.sourceBoxes)
        assertFalse(mapped.boundingBox.isEmpty)
        assertEquals(original.text, mapped.text)
        assertEquals(original.confidence, mapped.confidence, 0f)
    }

    private suspend fun seed(dao: GalleryTranslationDao, taskId: String, count: Int): List<GalleryTranslationItemEntity> {
        val settings = Settings(sourceLang = "ar", targetLang = "en", translatorEngine = TranslatorEngine.GOOGLE)
        val snapshot = TranslationPresetCatalog.fromSettings("gallery_$taskId", "owned", "owned", settings)
        val items = (0 until count).map { index -> GalleryTranslationItemEntity(
            id = "$taskId-$index", taskId = taskId, position = index,
            sourceUri = "", localPath = "", displayName = "owned-$index.jpg", updatedAtMs = 10,
        ) }
        dao.insertTaskWithItems(GalleryTranslationTaskEntity(
            id = taskId, createdAtMs = 10, sourceLang = "ar", targetLang = "en",
            ocrEngine = settings.ocrEngine.name, translatorEngine = settings.translatorEngine.name,
            presetName = "owned", settingsSnapshotJson = json.encodeToString(snapshot), totalCount = count,
        ), items)
        return items
    }

    private suspend fun complete(dao: GalleryTranslationDao, claim: GalleryTranslationItemEntity, text: String): Int =
        dao.completeItem(claim.id, claim.updatedAtMs, 80, 48, 80, 48, "owned", text, "[]", 10)

    private suspend fun withRoom(body: suspend (GalleryTranslationDao) -> Unit) {
        val database = Room.inMemoryDatabaseBuilder(context, GalleryTranslationDatabase::class.java).build()
        try { body(database.galleryTranslationDao()) } finally { database.close() }
    }

    private fun withOwnedImages(body: (File) -> Unit) {
        val directory = File(context.cacheDir, "gallery-owned-${UUID.randomUUID()}")
        check(directory.mkdir())
        try { body(directory) } finally { directory.deleteRecursively() }
    }

    private fun cornerJpeg(directory: File, orientation: Int, width: Int, height: Int): File {
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        try {
            val canvas = android.graphics.Canvas(bitmap)
            val paint = android.graphics.Paint()
            listOf(Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW).forEachIndexed { index, color ->
                paint.color = color
                val x = (index % 2) * width / 2f
                val y = (index / 2) * height / 2f
                canvas.drawRect(x, y, x + width / 2f, y + height / 2f, paint)
            }
            val file = File(directory, "exif-$orientation.jpg")
            file.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.JPEG, 100, it)) }
            ExifInterface(file).apply {
                setAttribute(ExifInterface.TAG_ORIENTATION, orientation.toString())
                saveAttributes()
            }
            return file
        } finally { bitmap.recycle() }
    }

    private fun imageItem(file: File) = GalleryTranslationItemEntity(
        id = "owned", taskId = "owned", position = 0, sourceUri = "", localPath = file.absolutePath,
        displayName = file.name, updatedAtMs = 0,
    )

    private fun corners(bitmap: Bitmap): List<Int> = listOf(
        bitmap.getPixel(4, 4), bitmap.getPixel(bitmap.width - 5, 4),
        bitmap.getPixel(4, bitmap.height - 5), bitmap.getPixel(bitmap.width - 5, bitmap.height - 5),
    )

    private fun assertColor(message: String, expected: Int, actual: Int) {
        assertTrue(message, abs(Color.red(expected) - Color.red(actual)) <= 35 &&
            abs(Color.green(expected) - Color.green(actual)) <= 35 && abs(Color.blue(expected) - Color.blue(actual)) <= 35)
    }
}
