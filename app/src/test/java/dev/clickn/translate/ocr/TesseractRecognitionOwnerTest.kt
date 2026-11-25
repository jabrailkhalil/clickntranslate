package dev.clickn.translate.ocr

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import org.junit.Assert.*
import org.junit.Test

class TesseractRecognitionOwnerTest {
    @Test fun cancellationBeforeNativeRecognitionCannotStartAndDoesNotCallAnUninitializedStop() {
        val stopped = AtomicInteger(); val released = AtomicInteger()
        val owner = TesseractRecognitionOwner { stopped.incrementAndGet(); Unit }
        owner.cancel()
        try { owner.begin(); fail("Cancelled native work started") } catch (_: CancellationException) { }
        assertEquals(0, stopped.get())
        owner.dispose { released.incrementAndGet() }; owner.dispose { fail("Double native release") }
        owner.cancel(); owner.progress()
        assertEquals(1, released.get()); assertEquals(0, stopped.get())
    }

    @Test fun cancellationStopsInFlightRecognitionButNeverReleasesItsResourcesFromTheCallerThread() {
        val stopped = AtomicInteger(); val released = AtomicInteger()
        val owner = TesseractRecognitionOwner { stopped.incrementAndGet(); Unit }
        owner.begin(); owner.cancel()
        assertTrue(stopped.get() > 0)
        assertEquals(0, released.get())
        try { owner.ensureActive(); fail("Partial native result would be published") } catch (_: CancellationException) { }
        owner.progress() // A cancelled JNI hOCR monitor may need its stop signal repeated.
        owner.dispose { released.incrementAndGet() }
        val drainedStops = stopped.get()
        owner.cancel(); owner.progress()
        assertEquals(drainedStops, stopped.get()); assertEquals(1, released.get())
    }

    @Test fun nativeReleaseCannotRaceAnAlreadyExecutingStopCall() {
        val stopEntered = CountDownLatch(1); val releaseStop = CountDownLatch(1)
        val attemptedDisposal = CountDownLatch(1); val disposed = CountDownLatch(1)
        val owner = TesseractRecognitionOwner { stopEntered.countDown(); check(releaseStop.await(5, TimeUnit.SECONDS)) }
        owner.begin()
        val cancellation = Thread { owner.cancel() }.apply { start() }
        assertTrue(stopEntered.await(5, TimeUnit.SECONDS))
        val worker = Thread { attemptedDisposal.countDown(); owner.dispose { disposed.countDown() } }.apply { start() }
        assertTrue(attemptedDisposal.await(5, TimeUnit.SECONDS))
        assertEquals(1L, disposed.count)
        releaseStop.countDown()
        cancellation.join(5_000); worker.join(5_000)
        assertFalse(cancellation.isAlive); assertFalse(worker.isAlive); assertEquals(0L, disposed.count)
    }
}
