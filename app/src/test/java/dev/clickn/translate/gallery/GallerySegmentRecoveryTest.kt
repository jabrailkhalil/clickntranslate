package dev.clickn.translate.gallery

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class GallerySegmentRecoveryTest {
    private val json = Json { encodeDefaults = true; ignoreUnknownKeys = true }

    @Test fun retryRequestsOnlyMissingParagraphsAndPreservesGoodResultAndOrder() = runTest {
        val blocks = listOf(segment("First paragraph.", "Первый абзац.", 0),
            segment("Second paragraph.", "", 1), segment("فقرة مستقلة", "", 2))
        var request: List<String>? = null
        val result = GallerySegmentRecovery.translateMissing(blocks) {
            request = it
            listOf("Второй абзац.", "Независимый абзац.")
        }
        assertEquals(listOf("Second paragraph.", "فقرة مستقلة"), request)
        assertEquals(blocks[0], result[0])
        assertEquals(blocks.map { it.sourceText }, result.map { it.sourceText })
        assertEquals(blocks.map { it.boundingBox }, result.map { it.boundingBox })
        assertEquals(listOf("Первый абзац.", "Второй абзац.", "Независимый абзац."), result.map { it.translatedText })
        assertTrue(GallerySegmentRecovery.missingIndices(result).isEmpty())
    }

    @Test fun nullBlankAndShortRepliesRemainMissingWithoutErasingGoodBlocks() = runTest {
        val blocks = listOf(segment("Good", "Готово", 0), segment("One", "", 1), segment("Two", "", 2))
        for (reply in listOf(emptyList(), listOf(null), listOf(" ", null))) {
            val result = GallerySegmentRecovery.translateMissing(blocks) { reply }
            assertEquals(listOf(1, 2), GallerySegmentRecovery.missingIndices(result))
            assertEquals(blocks[0], result[0])
        }
        assertEquals(GalleryTaskStatus.PARTIAL,
            GalleryTranslationWorkPolicy.terminalStatus(GalleryTaskProgress(1, 0, 1, partial = 1), false))
        assertEquals(GalleryTaskStatus.FAILED,
            GalleryTranslationWorkPolicy.terminalStatus(GalleryTaskProgress(1, 0, 1), false))
    }

    @Test fun completedSnapshotDoesNotCallTheProviderAgain() = runTest {
        val blocks = listOf(segment("First", "Первый", 0), segment("Second", "Второй", 1))
        val result = GallerySegmentRecovery.translateMissing(blocks) { error("Completed blocks must not be resubmitted") }
        assertEquals(blocks, result)
    }

    @Test fun cancellationCannotPublishAReplacementOfSavedPartialResults() = runTest {
        val blocks = listOf(segment("Good", "Готово", 0), segment("Pending", "", 1))
        val entered = CompletableDeferred<Unit>()
        var published: List<GalleryTranslationSegment>? = null
        val job = launch {
            published = GallerySegmentRecovery.translateMissing(blocks) {
                entered.complete(Unit)
                awaitCancellation()
            }
        }
        entered.await()
        job.cancelAndJoin()
        assertNull(published)
        assertEquals("Готово", blocks[0].translatedText)
        assertEquals("", blocks[1].translatedText)
    }

    @Test fun persistedRecognitionRequiresTheSamePrivateImageGeometry() {
        val blocks = listOf(segment("First", "Первый", 0), segment("Second", "", 1))
        val item = GalleryTranslationItemEntity(id = "image", taskId = "task", position = 0,
            sourceUri = "content://owned/image", localPath = "/owned/private.png", displayName = "own.png",
            processedWidth = 100, processedHeight = 100, segmentsJson = json.encodeToString(blocks), updatedAtMs = 1)
        assertEquals(blocks, GallerySegmentRecovery.resume(item, 100, 100, json))
        assertNull(GallerySegmentRecovery.resume(item, 100, 90, json))
        assertNull(GallerySegmentRecovery.resume(item.copy(localPath = ""), 100, 100, json))
        assertNull(GallerySegmentRecovery.resume(item.copy(segmentsJson = "invalid"), 100, 100, json))
    }

    @Test fun olderSegmentJsonGetsSafeDefaultsForNewRecognitionMetadata() {
        val old = """[{"sourceText":"Hello","translatedText":"","boundingBox":{"left":0,"top":0,"right":20,"bottom":20},"sourceBoxes":[],"confidence":1.0}]"""
        val restored = requireNotNull(GallerySegmentRecovery.decode(old, json)).single()
        assertNull(restored.regionId)
        assertNull(restored.regionGranularity)
        assertEquals(0, restored.presentationRotationDegrees)
        assertEquals(listOf(0), GallerySegmentRecovery.missingIndices(listOf(restored)))
    }

    @Test fun imageOnlyApiKeepsGoodMatchesButDoesNotMixDifferentRecognition() {
        val previous = listOf(segment("First", "Первый", 0), segment("Second", "", 1))
        val fresh = listOf(segment("First", "Changed duplicate", 0), segment("Second", "Второй", 1))
        val merged = GallerySegmentRecovery.mergeImageOnlyResult(previous, fresh)
        assertEquals(listOf("Первый", "Второй"), merged.map { it.translatedText })
        val changedRecognition = fresh.map { it.copy(boundingBox = it.boundingBox.copy(right = 80)) }
        assertEquals(changedRecognition, GallerySegmentRecovery.mergeImageOnlyResult(previous, changedRecognition))
    }

    private fun segment(source: String, target: String, index: Int) = GalleryTranslationSegment(
        source, target, GalleryRect(1, index * 25, 90, index * 25 + 20),
        listOf(GalleryRect(1, index * 25, 90, index * 25 + 20)), 0.95f,
    )
}
