package dev.clickn.translate.gallery

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslationPresetCatalog
import dev.clickn.translate.ui.galleryTaskElapsedSeconds
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Isolated real Room retry admission; no app queue, settings, credentials, OCR or HTTP. */
@RunWith(AndroidJUnit4::class)
class GalleryRetryProgressIntegrationTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test fun selectedRetryAtomicallyPublishesEighteenOfTwentyAndStartsANewElapsedInterval() = runBlocking {
        withRoom { dao ->
            val items = seed(dao, "selected", List(18) { GalleryItemStatus.SUCCEEDED } + List(2) { GalleryItemStatus.FAILED })
            val receipt = requireNotNull(dao.failedRetrySelection("selected"))
            withTimeout(5_000) {
                val observedInitial = CompletableDeferred<Unit>()
                val observed = async {
                    dao.observeTask("selected").filterNotNull().distinctUntilChanged()
                        .onEach { observedInitial.complete(Unit) }.take(2).toList()
                }
                observedInitial.await()
                val retryAt = 3_600_000L // Deliberately leave almost an hour idle after the first attempt.
                assertEquals(2, dao.resetSelectedFailures("selected", receipt, retryAt))
                val states = observed.await()
                assertEquals(listOf(GalleryTaskStatus.PARTIAL, GalleryTaskStatus.QUEUED), states.map { it.status })
                assertEquals(20, states[0].completedCount)
                val queued = states[1]
                assertEquals(20, queued.totalCount)
                assertEquals(18, queued.completedCount)
                assertEquals(18, queued.successCount)
                assertEquals(0, queued.failedCount)
                assertEquals(retryAt, queued.startedAtMs)
                assertNull(queued.finishedAtMs)
                assertEquals("", queued.lastError)
                assertEquals(2L, galleryTaskElapsedSeconds(queued.startedAtMs, queued.finishedAtMs, retryAt + 2_000))
                val stored = dao.getItems("selected")
                assertEquals(items.take(18), stored.take(18))
                assertTrue(stored.takeLast(2).all { it.status == GalleryItemStatus.QUEUED && it.attemptCount == 0 })
                assertTrue(stored.takeLast(2).zip(items.takeLast(2)).all { (next, old) -> next.updatedAtMs > old.updatedAtMs })
            }
        }
    }

    @Test fun resetAllFailuresPreservesSuccessAndCanceledRowsAndAutomaticRetryKeepsTheNewInterval() = runBlocking {
        withRoom { dao ->
            val items = seed(dao, "legacy", List(18) { GalleryItemStatus.SUCCEEDED } +
                listOf(GalleryItemStatus.FAILED, GalleryItemStatus.CANCELED))
            val retryAt = 7_200_000L
            assertEquals(1, dao.resetFailedTask("legacy", retryAt))
            val queued = requireNotNull(dao.getTask("legacy"))
            assertEquals(20, queued.totalCount)
            assertEquals(18, queued.completedCount)
            assertEquals(18, queued.successCount)
            assertEquals(0, queued.failedCount)
            assertEquals(retryAt, queued.startedAtMs)
            assertNull(queued.finishedAtMs)
            assertEquals(items.take(18), dao.getItems("legacy").take(18))
            assertEquals(items.last(), dao.getItems("legacy").last())

            assertEquals(1, dao.markTaskRunning("legacy", GalleryTaskStatus.RUNNING, retryAt + 500))
            val pending = requireNotNull(dao.getItem(items[18].id))
            val claim = requireNotNull(dao.claimItem(pending, retryAt + 600))
            assertEquals(1, dao.markItemFailed(claim.id, claim.updatedAtMs, GalleryItemStatus.QUEUED, "retryable", retryAt + 800))
            dao.markTaskWaitingRetry("legacy", "retryable")
            assertEquals(1, dao.markTaskRunning("legacy", GalleryTaskStatus.RUNNING, retryAt + 1_500))
            assertEquals(retryAt, dao.getTask("legacy")?.startedAtMs)
            val resumed = requireNotNull(dao.claimItem(requireNotNull(dao.getItem(claim.id)), retryAt + 1_600))
            assertEquals(0, complete(dao, claim, retryAt + 1_700))
            assertEquals(1, complete(dao, resumed, retryAt + 2_000))
            val progress = dao.progress("legacy")
            assertEquals(1, progress.canceled)
            assertEquals(19, progress.succeeded)
            assertEquals(GalleryTaskStatus.PARTIAL, GalleryTranslationWorkPolicy.terminalStatus(
                GalleryTaskProgress(progress.total, progress.succeeded, progress.failed, progress.canceled), false,
            ))
            // The normal worker refreshes progress before finalization.
            dao.updateProgress("legacy", progress.total, progress.succeeded + progress.failed,
                progress.succeeded, progress.failed, "")
            assertEquals(1, dao.finishTask("legacy", GalleryTaskStatus.PARTIAL, retryAt + 4_000, ""))
            val ended = requireNotNull(dao.getTask("legacy"))
            assertEquals(19, ended.completedCount)
            assertEquals(0, ended.failedCount)
            assertEquals(4L, galleryTaskElapsedSeconds(ended.startedAtMs, ended.finishedAtMs, retryAt + 99_000))
            assertEquals(items.last(), dao.getItems("legacy").last())
        }
    }

    @Test fun rejectedOrReplayedReceiptCannotResetCountersOrElapsedAndLaterCancelStillWins() = runBlocking {
        withRoom { dao ->
            val items = seed(dao, "guard", listOf(GalleryItemStatus.SUCCEEDED, GalleryItemStatus.FAILED, GalleryItemStatus.CANCELED))
            val stale = requireNotNull(dao.failedRetrySelection("guard"))
            dao.cancelTaskAndItems("guard", FIRST_FINISH)
            val canceled = requireNotNull(dao.getTask("guard"))
            val canceledItems = dao.getItems("guard")
            assertEquals(0, dao.resetSelectedFailures("guard", stale, 9_000_000))
            assertEquals(canceled, dao.getTask("guard"))
            assertEquals(canceledItems, dao.getItems("guard"))

            val accepted = requireNotNull(dao.failedRetrySelection("guard"))
            assertEquals(1, dao.resetSelectedFailures("guard", accepted, 10_000_000))
            val admitted = requireNotNull(dao.getTask("guard"))
            assertEquals(1, admitted.completedCount)
            assertEquals(0, admitted.failedCount)
            assertEquals(0, dao.resetSelectedFailures("guard", accepted, 11_000_000))
            assertEquals(admitted, dao.getTask("guard"))
            dao.cancelTaskAndItems("guard", 10_000_100)
            val canceledAgain = requireNotNull(dao.getTask("guard"))
            assertEquals(0, dao.resetSelectedFailures("guard", accepted, 12_000_000))
            assertEquals(canceledAgain, dao.getTask("guard"))
            assertEquals(items.first(), dao.getItems("guard").first())
            assertEquals(items.last(), dao.getItems("guard").last())
            assertEquals(GalleryItemStatus.CANCELED, dao.getItems("guard")[1].status)
        }
    }

    @Test fun noFailedRowsLeavesThePriorCompletedIntervalAndProgressUntouched() = runBlocking {
        withRoom { dao ->
            val items = seed(dao, "nothing", List(19) { GalleryItemStatus.SUCCEEDED } + GalleryItemStatus.CANCELED)
            val task = requireNotNull(dao.getTask("nothing"))
            assertEquals(0, dao.resetFailedTask("nothing", 9_000_000))
            assertEquals(0, dao.resetSelectedFailures("nothing", GalleryRetrySelection(
                task.status, requireNotNull(task.finishedAtMs), emptyList(),
            ), 10_000_000))
            assertEquals(task, dao.getTask("nothing"))
            assertEquals(items, dao.getItems("nothing"))
            assertEquals(4L, galleryTaskElapsedSeconds(task.startedAtMs, task.finishedAtMs, 20_000_000))
        }
    }

    private suspend fun seed(
        dao: GalleryTranslationDao,
        id: String,
        statuses: List<GalleryItemStatus>,
    ): List<GalleryTranslationItemEntity> {
        val settings = Settings()
        val succeeded = statuses.count { it == GalleryItemStatus.SUCCEEDED }
        val failed = statuses.count { it == GalleryItemStatus.FAILED }
        val items = statuses.mapIndexed { index, status -> GalleryTranslationItemEntity(
            id = "$id-$index", taskId = id, position = index, sourceUri = "", localPath = "",
            displayName = "owned-$index.png", status = status, attemptCount = 3,
            sourceText = "owned source $index", translatedText = if (status == GalleryItemStatus.SUCCEEDED) "owned $index" else "",
            errorMessage = if (status == GalleryItemStatus.FAILED) "owned failure" else "", updatedAtMs = FIRST_FINISH + index,
        ) }
        dao.insertTaskWithItems(GalleryTranslationTaskEntity(
            id = id, createdAtMs = 1_000, startedAtMs = 2_000, finishedAtMs = FIRST_FINISH,
            status = GalleryTaskStatus.PARTIAL, sourceLang = settings.sourceLang, targetLang = settings.targetLang,
            ocrEngine = settings.ocrEngine.name, translatorEngine = settings.translatorEngine.name, presetName = "owned",
            settingsSnapshotJson = Json.encodeToString(TranslationPresetCatalog.fromSettings("gallery_$id", "owned", "owned", settings)),
            totalCount = items.size, completedCount = succeeded + failed, successCount = succeeded, failedCount = failed,
            lastError = if (failed > 0) "owned failure" else "",
        ), items)
        return items
    }

    private suspend fun complete(dao: GalleryTranslationDao, item: GalleryTranslationItemEntity, now: Long): Int =
        dao.completeItem(item.id, item.updatedAtMs, 80, 48, 80, 48, "owned", "translated", "[]", now)

    private suspend fun withRoom(body: suspend (GalleryTranslationDao) -> Unit) {
        val database = Room.inMemoryDatabaseBuilder(context, GalleryTranslationDatabase::class.java).build()
        try { body(database.galleryTranslationDao()) } finally { database.close() }
    }

    private companion object { const val FIRST_FINISH = 6_000L }
}
