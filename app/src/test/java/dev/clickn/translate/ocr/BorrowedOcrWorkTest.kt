package dev.clickn.translate.ocr

import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class BorrowedOcrWorkTest {
    @Test fun cancelledCallerRetainsItsPixelsUntilNativeWorkCompletesAndNeverPublishes() = runBlocking {
        val nativeComplete = CompletableDeferred<Unit>()
        val pixelsRetired = AtomicBoolean()
        val published = AtomicBoolean()
        val nativeRead = AtomicBoolean()
        val caller = async(start = CoroutineStart.UNDISPATCHED) {
            try {
                finishBorrowedOcrWork {
                    nativeComplete.await()
                    assertFalse("Caller recycled pixels while native Task still owned them", pixelsRetired.get())
                    nativeRead.set(true)
                    "obsolete text"
                }
                published.set(true)
            } finally { pixelsRetired.set(true) }
        }
        caller.cancel()
        assertFalse(caller.isCompleted)
        assertFalse(pixelsRetired.get())
        nativeComplete.complete(Unit)
        caller.join()
        assertTrue(nativeRead.get()); assertTrue(pixelsRetired.get()); assertFalse(published.get())
    }

    @Test fun failedNativeTaskReleasesTheCallerWithoutPublishingPartialText() = runBlocking {
        val nativeComplete = CompletableDeferred<Unit>()
        val retired = AtomicBoolean()
        val failure = IllegalArgumentException("native OCR failed")
        val caller = async(start = CoroutineStart.UNDISPATCHED) {
            try { finishBorrowedOcrWork { nativeComplete.await(); throw failure } }
            catch (error: IllegalArgumentException) {
                // Coroutine stack-trace recovery may copy an exception while retaining its contract.
                assertEquals(failure.javaClass, error.javaClass)
                assertEquals(failure.message, error.message)
            }
            finally { retired.set(true) }
        }
        assertFalse(retired.get())
        nativeComplete.complete(Unit)
        caller.await()
        assertTrue(retired.get())
    }
}
