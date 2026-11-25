package dev.clickn.translate.capture

import dev.clickn.translate.service.TranslationBatchGate
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/** Pure lifetime/race coverage; real MediaProjection rotation remains a device test. */
class CaptureGeometryBarrierTest {
    @Test
    fun initialAndDuplicateCallbacksKeepTheActiveResultIncludingDifferentCaptureExtent() {
        val geometry = CaptureGeometryBarrier()
        val retired = AtomicInteger()
        assertFalse(geometry.observeDisplay(1080, 2400) { retired.incrementAndGet() })
        val generation = geometry.snapshot()
        assertTrue(geometry.bindBatch(7L, generation))
        assertFalse(geometry.acceptsBatch(null))
        // The initial platform callback can describe an app window rather than the full display.
        assertFalse(geometry.observeCapture(900, 1800) { retired.incrementAndGet() })
        repeat(3) {
            assertFalse(geometry.observeDisplay(1080, 2400) { retired.incrementAndGet() })
            assertFalse(geometry.observeCapture(900, 1800) { retired.incrementAndGet() })
        }
        assertFalse(geometry.observeCapture(0, 1800) { retired.incrementAndGet() })
        assertFalse(geometry.observeDisplay(1080, -1) { retired.incrementAndGet() })
        assertEquals(0, retired.get())
        assertTrue(geometry.isCurrent(generation))
        assertTrue(geometry.acceptsBatch(7L))
    }

    @Test
    fun displayRotationRejectsTheOldFrameAndAllowsANewAttempt() {
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(1080, 2400)
        val portrait = geometry.snapshot()
        assertTrue(geometry.bindBatch(1L, portrait))
        assertTrue(geometry.observeDisplay(2400, 1080))
        assertFalse(geometry.isCurrent(portrait))
        assertFalse(geometry.acceptsBatch(1L))
        assertFalse(geometry.bindBatch(2L, portrait))
        assertTrue(geometry.bindBatch(3L, geometry.snapshot()))
        assertTrue(geometry.acceptsBatch(3L))
    }

    @Test
    fun capturedContentResizeRetiresWorkEvenWhenPhysicalDisplayHasNotChanged() {
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(2400, 1080)
        geometry.observeCapture(1200, 900)
        val original = geometry.snapshot()
        geometry.bindBatch(11L, original)
        assertTrue(geometry.observeCapture(900, 900))
        assertFalse(geometry.observeDisplay(2400, 1080))
        assertFalse(geometry.acceptsBatch(11L))
        assertTrue(geometry.bindBatch(12L, geometry.snapshot()))
        assertFalse(geometry.observeCapture(900, 900))
        assertTrue(geometry.acceptsBatch(12L))
    }

    @Test
    fun ocrReadyBeforeRotationIsRejectedAtTheQueuedPublicationBoundary() {
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(1080, 2400)
        geometry.bindBatch(1L, geometry.snapshot())
        val mainQueue = ArrayDeque<() -> Unit>()
        val published = mutableListOf<String>()
        assertTrue("Background OCR has completed before dispatch", geometry.acceptsBatch(1L))
        mainQueue.add { if (geometry.acceptsBatch(1L)) published += "old OCR" }
        geometry.observeDisplay(2400, 1080)
        mainQueue.removeFirst().invoke()
        assertTrue(published.isEmpty())
        geometry.bindBatch(2L, geometry.snapshot())
        mainQueue.add { if (geometry.acceptsBatch(2L)) published += "new OCR" }
        mainQueue.removeFirst().invoke()
        assertEquals(listOf("new OCR"), published)
    }

    @Test
    fun lateTranslationCannotPublishWhileItsOldBatchIdStillExistsInTheOtherGate() {
        val geometry = CaptureGeometryBarrier()
        val batches = TranslationBatchGate()
        geometry.observeCapture(1080, 2400)
        geometry.bindBatch(30L, geometry.snapshot())
        batches.activate(30L)
        geometry.observeCapture(2400, 1080)
        assertTrue("Tests the interval before the owner's other gate is invalidated", batches.accepts(30L))
        assertFalse(batches.accepts(30L) && geometry.acceptsBatch(30L))
        batches.invalidate()
        geometry.bindBatch(31L, geometry.snapshot())
        batches.activate(31L)
        assertTrue(batches.accepts(31L) && geometry.acceptsBatch(31L))
    }

    @Test
    fun suspendedOldAdmissionCannotOverwriteTheSuccessorBatch() {
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(1080, 2400)
        val oldSnapshot = geometry.snapshot()
        val resume = CountDownLatch(1)
        val worker = Executors.newSingleThreadExecutor()
        try {
            val oldAdmission = worker.submit<Boolean> {
                assertTrue(resume.await(2, TimeUnit.SECONDS))
                geometry.bindBatch(1L, oldSnapshot)
            }
            geometry.observeDisplay(2400, 1080)
            assertTrue(geometry.bindBatch(2L, geometry.snapshot()))
            resume.countDown()
            assertFalse(oldAdmission.get(2, TimeUnit.SECONDS))
            assertTrue(geometry.acceptsBatch(2L))
        } finally {
            resume.countDown()
            worker.shutdownNow()
        }
    }

    @Test
    fun retirementFinishesBeforeANewGenerationCanBeBound() {
        val geometry = CaptureGeometryBarrier()
        val retirementEntered = CountDownLatch(1)
        val finishRetirement = CountDownLatch(1)
        val admissionStarted = CountDownLatch(1)
        val owner = Executors.newSingleThreadExecutor()
        val worker = Executors.newSingleThreadExecutor()
        geometry.observeDisplay(1080, 2400)
        try {
            val retirement = owner.submit<Boolean> {
                geometry.observeDisplay(2400, 1080) {
                    retirementEntered.countDown()
                    assertTrue(finishRetirement.await(2, TimeUnit.SECONDS))
                }
            }
            assertTrue(retirementEntered.await(2, TimeUnit.SECONDS))
            val admission = worker.submit<Boolean> {
                admissionStarted.countDown()
                geometry.bindBatch(5L, geometry.snapshot())
            }
            assertTrue(admissionStarted.await(2, TimeUnit.SECONDS))
            try {
                admission.get(100, TimeUnit.MILLISECONDS)
                fail("A successor was admitted before the owner finished retiring the old work")
            } catch (_: TimeoutException) {
                // The owner still holds the short retirement boundary.
            }
            finishRetirement.countDown()
            assertTrue(retirement.get(2, TimeUnit.SECONDS))
            assertTrue(admission.get(2, TimeUnit.SECONDS))
            assertTrue(geometry.acceptsBatch(5L))
        } finally {
            finishRetirement.countDown()
            owner.shutdownNow()
            worker.shutdownNow()
        }
    }

    @Test
    fun rejectedAttemptDoesNotCancelItsPollingCoroutineAndNextAttemptIsAccepted() = runBlocking {
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(1080, 2400)
        val loop = currentCoroutineContext()[Job]
        val oldFrame = geometry.snapshot()
        geometry.observeDisplay(2400, 1080)
        assertFalse(geometry.bindBatch(1L, oldFrame))
        assertTrue(currentCoroutineContext().isActive)
        assertSame(loop, currentCoroutineContext()[Job])
        assertTrue(geometry.bindBatch(2L, geometry.snapshot()))
        assertTrue(geometry.acceptsBatch(2L))
    }
}
