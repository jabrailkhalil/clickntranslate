package dev.clickn.translate.ui

import dev.clickn.translate.data.Settings
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class GalleryImportSessionTest {
    @Test fun aRecreatedObserverConsumesOneCompletedImportUsingTheReviewedUrisAndSettings() = runTest {
        val gate = CompletableDeferred<String>()
        val reviewed = GallerySubmission(listOf("content://fixture/first"), Settings(targetLang = "fr"))
        var creates = 0
        val session = GalleryImportSession(backgroundScope) {
            creates++
            assertSame(reviewed, it)
            gate.await()
        }
        session.pendingSubmission = reviewed
        session.start(reviewed)
        val request = requireNotNull(session.preparation)
        assertNull(session.pendingSubmission)
        val originalObserver = launch { request.await(); fail("The detached screen consumed the result") }
        runCurrent()
        originalObserver.cancelAndJoin()
        assertTrue(request.isActive)
        session.start(GallerySubmission(listOf("content://fixture/second"), Settings(targetLang = "de")))
        assertSame(request, session.preparation)
        gate.complete("fixture-task")
        runCurrent()
        val afterRotation = requireNotNull(session.preparation)
        assertEquals("fixture-task", afterRotation.await())
        assertTrue(session.consume(afterRotation))
        assertFalse(session.consume(afterRotation))
        assertEquals(1, creates)
        assertNull(session.preparation)
    }

    @Test fun backingOutDiscardsConfirmationAndCancelsOnlyItsOwnPreparation() = runTest {
        val gate = CompletableDeferred<String>()
        val session = GalleryImportSession(backgroundScope) { gate.await() }
        val first = GallerySubmission(listOf("content://fixture/first"), Settings())
        session.pendingSubmission = first
        session.close()
        assertNull(session.pendingSubmission)
        session.start(first)
        val previous = requireNotNull(session.preparation)
        runCurrent()
        session.close()
        assertTrue(previous.isCancelled)
        session.start(GallerySubmission(listOf("content://fixture/second"), Settings()))
        val next = requireNotNull(session.preparation)
        assertNotSame(previous, next)
        assertFalse(session.consume(previous))
        gate.complete("next-task")
        runCurrent()
        assertEquals("next-task", next.await())
        assertTrue(session.consume(next))
    }
}
