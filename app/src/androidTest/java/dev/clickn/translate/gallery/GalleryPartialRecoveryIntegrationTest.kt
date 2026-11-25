package dev.clickn.translate.gallery

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Rect
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.ocr.TextBlock
import dev.clickn.translate.ocr.TextOrientation
import dev.clickn.translate.ocr.TextRegionGranularity
import java.io.File
import java.util.UUID
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real isolated Room/PNG/Rect recovery, with synthetic OCR and translation results only. */
@RunWith(AndroidJUnit4::class)
class GalleryPartialRecoveryIntegrationTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext
    private val json = Json { ignoreUnknownKeys = true }

    @Test fun partialImageRetainsItsFirstParagraphAndRetriesOnlyTheMissingSecondParagraph() = runBlocking {
        withStore { store ->
            val queued = store.seed("partial")
            assertEquals(1, store.dao.markTaskRunning(queued.taskId, GalleryTaskStatus.RUNNING, 4_000))
            val claim = requireNotNull(store.dao.claimItem(queued, 4_100))
            val decoder = GalleryImageDecoder(context)
            val decoded = decoder.decode(claim)
            try {
                val sources = syntheticBlocks().map { GalleryTranslationSegment.from(it, null) }
                val firstRequests = mutableListOf<List<String>>()
                val partial = GallerySegmentRecovery.translateMissing(sources) { request ->
                    firstRequests += request
                    listOf("Первый абзац переведён.", null)
                }
                assertEquals(listOf(sources.map { it.sourceText }), firstRequests)
                assertEquals(listOf(1), GallerySegmentRecovery.missingIndices(partial))
                assertEquals(1, writeResult(store.dao, claim, partial, 5_000, GalleryItemStatus.RUNNING))
                val checkpoint = requireNotNull(store.dao.getItem(claim.id))
                assertEquals(GalleryItemStatus.RUNNING, checkpoint.status)
                assertEquals(partial, requireNotNull(GallerySegmentRecovery.resume(
                    checkpoint, decoded.bitmap.width, decoded.bitmap.height, json,
                )))
                // The checkpoint owns a new version; the pre-checkpoint claim cannot fail it.
                assertEquals(0, store.dao.markItemFailed(claim.id, claim.updatedAtMs,
                    GalleryItemStatus.FAILED, "stale failure", 5_100))
                assertEquals(1, store.dao.markItemFailed(checkpoint.id, checkpoint.updatedAtMs,
                    GalleryItemStatus.FAILED, "Translated 1/2", 6_000))
                assertEquals(GalleryTaskStatus.PARTIAL, finish(store.dao, claim.taskId, 7_000, "Translated 1/2"))
                val progress = store.dao.progress(claim.taskId)
                assertEquals(1, progress.total)
                assertEquals(0, progress.succeeded)
                assertEquals(1, progress.failed)
                assertEquals(1, progress.partial)
                assertEquals(GalleryItemStatus.FAILED, store.dao.getItem(claim.id)?.status)
                val retry = requireNotNull(store.dao.failedRetrySelection(claim.taskId))
                assertEquals(listOf(claim.id), retry.items.map { it.id })
                assertEquals(GalleryTaskStatus.PARTIAL, retry.taskStatus)
                assertEquals(1, store.dao.resetSelectedFailures(claim.taskId, retry, 8_000))
                assertEquals(1, store.dao.markTaskRunning(claim.taskId, GalleryTaskStatus.RUNNING, 8_100))
                val resumedClaim = requireNotNull(store.dao.claimItem(
                    requireNotNull(store.dao.getItem(claim.id)), 8_200,
                ))
                val saved = requireNotNull(GallerySegmentRecovery.resume(
                    resumedClaim, decoded.bitmap.width, decoded.bitmap.height, json,
                ))
                val retryRequests = mutableListOf<List<String>>()
                val completed = GallerySegmentRecovery.translateMissing(saved) { request ->
                    retryRequests += request
                    listOf("Второй абзац переведён.")
                }
                assertEquals(listOf(listOf(sources[1].sourceText)), retryRequests)
                assertEquals(partial[0], completed[0])
                assertEquals(sources[1].copy(translatedText = "Второй абзац переведён."), completed[1])
                assertTrue(GallerySegmentRecovery.missingIndices(completed).isEmpty())
                assertEquals(1, writeResult(store.dao, resumedClaim, completed, 9_000))
                assertEquals(GalleryTaskStatus.SUCCEEDED, finish(store.dao, claim.taskId, 10_000))
                val final = requireNotNull(store.dao.getItem(claim.id))
                assertEquals(GalleryItemStatus.SUCCEEDED, final.status)
                assertEquals(completed, GallerySegmentRecovery.decode(final.segmentsJson, json))
                assertEquals("Первый абзац переведён.\nВторой абзац переведён.", final.translatedText)
                assertNull(store.dao.failedRetrySelection(claim.taskId))
                assertEquals(0, store.dao.progress(claim.taskId).partial)
            } finally {
                decoded.bitmap.recycle()
            }
        }
    }

    @Test fun fileBackedRestartReclaimsTheCheckpointWithoutLosingOcrOrAcceptingTheOldClaim() = runBlocking {
        withStore { store ->
            val queued = store.seed("restart")
            assertEquals(1, store.dao.markTaskRunning(queued.taskId, GalleryTaskStatus.RUNNING, 4_000))
            val claim = requireNotNull(store.dao.claimItem(queued, 4_100))
            val partial = syntheticBlocks().mapIndexed { index, block ->
                GalleryTranslationSegment.from(block, if (index == 0) "Сохранённый перевод." else null)
            }
            assertEquals(1, writeResult(store.dao, claim, partial, 5_000, GalleryItemStatus.RUNNING))
            val beforeRestart = requireNotNull(store.dao.getItem(claim.id))
            val imageBytes = store.image.readBytes()
            store.reopen()
            assertEquals(beforeRestart, store.dao.getItem(claim.id))
            store.dao.resetInterruptedItems(claim.taskId, 6_000)
            val reclaimed = requireNotNull(store.dao.getItem(claim.id))
            assertEquals(beforeRestart.copy(status = GalleryItemStatus.QUEUED, updatedAtMs = reclaimed.updatedAtMs), reclaimed)
            assertTrue(reclaimed.updatedAtMs > beforeRestart.updatedAtMs)
            assertNull(store.dao.claimItem(beforeRestart, 6_100))
            val newClaim = requireNotNull(store.dao.claimItem(reclaimed, 6_200))
            assertEquals(0, writeResult(store.dao, beforeRestart, partial, 6_300))
            assertEquals(0, store.dao.markItemFailed(beforeRestart.id, beforeRestart.updatedAtMs,
                GalleryItemStatus.FAILED, "late old result", 6_400))
            assertEquals(newClaim, store.dao.getItem(claim.id))
            val decoded = GalleryImageDecoder(context).decode(newClaim)
            try {
                assertEquals(partial, GallerySegmentRecovery.resume(newClaim, decoded.bitmap.width, decoded.bitmap.height, json))
                assertEquals(listOf(1), GallerySegmentRecovery.missingIndices(partial))
            } finally {
                decoded.bitmap.recycle()
            }
            assertArrayEquals(imageBytes, store.image.readBytes())
        }
    }

    @Test fun legacyFalseSuccessBecomesRetryableWithoutLosingContentGeometryOrItsFinishTime() = runBlocking {
        withStore { store ->
            val segments = syntheticBlocks().mapIndexed { index, block ->
                GalleryTranslationSegment.from(block, if (index == 0) "Старый полезный перевод." else null)
            }
            val old = store.seed("legacy", GalleryTaskStatus.SUCCEEDED, GalleryItemStatus.SUCCEEDED, segments)
            val oldTask = requireNotNull(store.dao.getTask(old.taskId))
            val repairer = repair(store.dao)
            repairer.run()
            val repaired = requireNotNull(store.dao.getItem(old.id))
            assertEquals(old.copy(status = GalleryItemStatus.FAILED, errorMessage = "Translated 1/2",
                updatedAtMs = repaired.updatedAtMs), repaired)
            assertTrue(repaired.updatedAtMs > old.updatedAtMs)
            assertEquals(oldTask.copy(status = GalleryTaskStatus.PARTIAL, successCount = 0,
                failedCount = 1, lastError = "Translated 1/2"), store.dao.getTask(old.taskId))
            assertEquals(1, store.dao.progress(old.taskId).partial)
            assertNotNull(store.dao.failedRetrySelection(old.taskId))
            val repairedTask = requireNotNull(store.dao.getTask(old.taskId))
            repairer.repairTask(old.taskId)
            repair(store.dao).run() // A new scanner must also be idempotent.
            assertEquals(repaired, store.dao.getItem(old.id))
            assertEquals(repairedTask, store.dao.getTask(old.taskId))
            assertFalse(store.dao.repairIncompleteResult(old, "stale repair", 99_000))
            assertEquals(repaired, store.dao.getItem(old.id))
        }
    }

    @Test fun repairLeavesCanceledAndActiveTasksAloneAndCanRepairOneThatFinishesAfterTheScan() = runBlocking {
        withStore { store ->
            val partial = syntheticBlocks().mapIndexed { index, block ->
                GalleryTranslationSegment.from(block, if (index == 0) "Сохранено." else null)
            }
            val canceled = store.seed("canceled", GalleryTaskStatus.CANCELED, GalleryItemStatus.SUCCEEDED, partial)
            val active = store.seed("active", GalleryTaskStatus.RUNNING, GalleryItemStatus.SUCCEEDED, partial)
            val canceledTask = requireNotNull(store.dao.getTask(canceled.taskId))
            val activeTask = requireNotNull(store.dao.getTask(active.taskId))
            val repairer = repair(store.dao)
            repairer.run()
            repairer.repairTask(canceled.taskId)
            repairer.repairTask(active.taskId)
            assertEquals(canceledTask, store.dao.getTask(canceled.taskId))
            assertEquals(canceled, store.dao.getItem(canceled.id))
            assertEquals(activeTask, store.dao.getTask(active.taskId))
            assertEquals(active, store.dao.getItem(active.id))
            assertEquals(1, store.dao.finishTask(active.taskId, GalleryTaskStatus.SUCCEEDED, 12_345, ""))
            repairer.repairTask(active.taskId)
            val repaired = requireNotNull(store.dao.getTask(active.taskId))
            assertEquals(GalleryTaskStatus.PARTIAL, repaired.status)
            assertEquals(12_345L, repaired.finishedAtMs)
            assertEquals(GalleryItemStatus.FAILED, store.dao.getItem(active.id)?.status)
            assertEquals(partial, GallerySegmentRecovery.decode(requireNotNull(store.dao.getItem(active.id)).segmentsJson, json))
            assertEquals(canceledTask, store.dao.getTask(canceled.taskId))
            assertEquals(canceled, store.dao.getItem(canceled.id))
        }
    }

    @Test fun persistedSegmentsRestoreRealAndroidRectsRegionsOrientationsAndPresentationRotation() = runBlocking {
        withStore { store ->
            val blocks = syntheticBlocks()
            val segments = blocks.map { GalleryTranslationSegment.from(it, "Синтетический перевод.") }
            val item = store.seed("geometry", GalleryTaskStatus.SUCCEEDED, GalleryItemStatus.SUCCEEDED, segments)
            store.reopen()
            val saved = requireNotNull(store.dao.getItem(item.id))
            val restoredSegments = requireNotNull(GallerySegmentRecovery.resume(saved, WIDTH, HEIGHT, json))
            assertEquals(blocks, restoredSegments.map(::restoreGalleryTextBlock))
            assertEquals(listOf(Rect(8, 8, 210, 52), Rect(8, 76, 214, 128)),
                restoredSegments.map(::restoreGalleryTextBlock).map { it.boundingBox })
            assertEquals(listOf(TextOrientation.HORIZONTAL_RTL, TextOrientation.VERTICAL_RTL),
                restoredSegments.map(::restoreGalleryTextBlock).map { it.layoutOrientation })
        }
    }

    private fun repair(dao: GalleryTranslationDao) = GalleryLegacyResultRepair(dao, json) { translated, total ->
        "Translated $translated/$total"
    }

    private suspend fun finish(dao: GalleryTranslationDao, taskId: String, now: Long, message: String = ""): GalleryTaskStatus {
        val row = dao.progress(taskId)
        val progress = GalleryTaskProgress(row.total, row.succeeded, row.failed, row.canceled, row.partial)
        val status = GalleryTranslationWorkPolicy.terminalStatus(progress, false)
        dao.updateProgress(taskId, progress.total, progress.completed, progress.succeeded, progress.failed, message)
        assertEquals(1, dao.finishTask(taskId, status, now, message))
        return requireNotNull(dao.getTask(taskId)).status
    }

    private suspend fun writeResult(
        dao: GalleryTranslationDao,
        item: GalleryTranslationItemEntity,
        segments: List<GalleryTranslationSegment>,
        now: Long,
        status: GalleryItemStatus = GalleryItemStatus.SUCCEEDED,
    ): Int = dao.completeItem(
        item.id, item.updatedAtMs, WIDTH, HEIGHT, WIDTH, HEIGHT,
        segments.joinToString("\n") { it.sourceText },
        segments.filter { it.translatedText.isNotBlank() }.joinToString("\n") { it.translatedText },
        json.encodeToString(segments), now, status,
    )

    private fun syntheticBlocks() = listOf(
        TextBlock(
            text = "First synthetic paragraph.", boundingBox = Rect(8, 8, 210, 52), confidence = 0.97f,
            recognizedLanguage = "ar", layoutOrientation = TextOrientation.HORIZONTAL_RTL,
            sourceBoxes = listOf(Rect(8, 8, 180, 26), Rect(8, 30, 210, 52)),
            bubbleGroupId = 7, regionId = 11, parentRegionId = 3,
            regionGranularity = TextRegionGranularity.PARAGRAPH, presentationRotationDegrees = 90,
        ),
        TextBlock(
            text = "Second synthetic paragraph.", boundingBox = Rect(8, 76, 214, 128), confidence = 0.91f,
            recognizedLanguage = "ja", layoutOrientation = TextOrientation.VERTICAL_RTL,
            sourceBoxes = listOf(Rect(164, 76, 184, 128), Rect(190, 76, 214, 128)),
            bubbleGroupId = 9, regionId = 12, parentRegionId = 4,
            regionGranularity = TextRegionGranularity.BUBBLE, presentationRotationDegrees = 270,
        ),
    )

    private suspend fun withStore(body: suspend (Store) -> Unit) {
        val store = Store(context)
        try { body(store) } finally { store.close() }
    }

    private inner class Store(private val appContext: Context) {
        private val base = File(appContext.cacheDir, "gallery-partial-${UUID.randomUUID()}").apply { check(mkdirs()) }
        private val databaseFile = File(base, "fixture.db")
        val image = File(base, "synthetic.png")
        private var database = openDatabase()
        val dao: GalleryTranslationDao get() = database.galleryTranslationDao()

        init {
            val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
            try {
                bitmap.eraseColor(Color.WHITE)
                image.outputStream().use { check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
            } finally { bitmap.recycle() }
        }

        suspend fun seed(
            id: String,
            taskStatus: GalleryTaskStatus = GalleryTaskStatus.QUEUED,
            itemStatus: GalleryItemStatus = GalleryItemStatus.QUEUED,
            segments: List<GalleryTranslationSegment> = emptyList(),
        ): GalleryTranslationItemEntity {
            val succeeded = if (itemStatus == GalleryItemStatus.SUCCEEDED) 1 else 0
            val failed = if (itemStatus == GalleryItemStatus.FAILED) 1 else 0
            val terminal = taskStatus in setOf(GalleryTaskStatus.SUCCEEDED, GalleryTaskStatus.PARTIAL,
                GalleryTaskStatus.FAILED, GalleryTaskStatus.CANCELED)
            val item = GalleryTranslationItemEntity(
                id = "$id-image", taskId = id, position = 0, sourceUri = "", localPath = image.absolutePath,
                displayName = "synthetic.png", status = itemStatus, attemptCount = 0,
                originalWidth = WIDTH, originalHeight = HEIGHT, processedWidth = WIDTH, processedHeight = HEIGHT,
                sourceText = segments.joinToString("\n") { it.sourceText },
                translatedText = segments.filter { it.translatedText.isNotBlank() }.joinToString("\n") { it.translatedText },
                segmentsJson = json.encodeToString(segments), updatedAtMs = 3_000,
            )
            dao.insertTaskWithItems(GalleryTranslationTaskEntity(
                id = id, createdAtMs = 1_000, startedAtMs = 2_000, finishedAtMs = if (terminal) 3_500 else null,
                status = taskStatus, sourceLang = "en", targetLang = "ru", ocrEngine = "ML_KIT_LATIN",
                translatorEngine = "LIBRETRANSLATE", presetName = "owned synthetic", settingsSnapshotJson = "{}",
                totalCount = 1, completedCount = succeeded + failed, successCount = succeeded, failedCount = failed,
            ), listOf(item))
            return item
        }

        fun reopen() {
            database.close()
            database = openDatabase()
        }

        private fun openDatabase() = Room.databaseBuilder(appContext,
            GalleryTranslationDatabase::class.java, databaseFile.absolutePath).build()

        fun close() {
            database.close()
            check(base.canonicalFile.parentFile == appContext.cacheDir.canonicalFile)
            check(base.deleteRecursively())
        }
    }

    private companion object {
        const val WIDTH = 240
        const val HEIGHT = 160
    }
}
