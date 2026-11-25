package dev.clickn.translate.translate

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import org.junit.Assert.*
import org.junit.Test

/** Real production request owner with deferred backends; no source-marker/UI-string assertions. */
class ProcessTextReviewSessionTest {
    @Test fun reattachmentKeepsOnePendingRequestAndItsCompletedEditableResult() = runBlocking {
        var calls = 0
        val answer = CompletableDeferred<String>()
        val session = ProcessTextReviewSession(this) { source ->
            calls++
            assertEquals("  Selected text  ", source)
            ProcessTextTranslationPresentation(answer.await(), true)
        }
        try {
            session.start("  Selected text  ", readOnly = false)
            yield()
            assertEquals(1, calls)
            assertNull("Loading text cannot be returned as a replacement", session.replacement())
            session.start("  Selected text  ", readOnly = false, translateNow = false)
            assertEquals(1, calls)
            answer.complete("Переведённый текст")
            val ready = withTimeout(2_000) { session.state.first { it?.succeeded == true } }
            session.start("  Selected text  ", readOnly = false, translateNow = false)
            assertEquals(ready, session.state.value)
            assertEquals(1, calls)
            assertEquals("Переведённый текст", session.replacement())
            assertEquals("Переведённый текст", session.copyText())
        } finally { answer.complete("late"); session.close() }
    }

    @Test fun readOnlyResultIsCopyableButCanNeverReplaceTheCallingEditorsSelection() = runBlocking {
        val session = ProcessTextReviewSession(this) { ProcessTextTranslationPresentation("مرحبا Android", true) }
        try {
            session.start("Hello Android", readOnly = true)
            withTimeout(2_000) { session.state.first { it?.succeeded == true } }
            assertEquals("مرحبا Android", session.copyText())
            assertNull(session.replacement())
            session.close()
            assertNull(session.copyText())
            assertNull(session.replacement())
        } finally { session.close() }
    }

    @Test fun realCloseCancelsPendingBackendAndNeverPublishesItsStatusOrFailureAsText() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val cancelled = CompletableDeferred<Unit>()
        val session = ProcessTextReviewSession(this) {
            entered.complete(Unit)
            try { awaitCancellation() } finally { cancelled.complete(Unit) }
        }
        try {
            session.start("User selection", readOnly = false)
            withTimeout(2_000) { entered.await() }
            session.close()
            withTimeout(2_000) { cancelled.await() }
            assertTrue(requireNotNull(session.state.value).closed)
            assertFalse(requireNotNull(session.state.value).busy)
            assertFalse(requireNotNull(session.state.value).failed)
            assertNull(session.copyText())
            assertNull(session.replacement())
        } finally { session.close() }
    }

    @Test fun nonCooperativeLateBackendCannotResurrectAClosedReview() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val returned = CompletableDeferred<Unit>()
        val session = ProcessTextReviewSession(this) {
            entered.complete(Unit)
            withContext(NonCancellable) {
                release.await()
                returned.complete(Unit)
            }
            ProcessTextTranslationPresentation("obsolete translation", true)
        }
        try {
            session.start("Original selection", readOnly = false)
            withTimeout(2_000) { entered.await() }
            session.close()
            val closed = session.state.value
            release.complete(Unit)
            withTimeout(2_000) { returned.await() }
            yield()
            assertEquals(closed, session.state.value)
            assertNull(session.replacement())
            assertNull(session.copyText())
            session.start("Queued old intent", readOnly = false)
            session.retry()
            assertEquals(closed, session.state.value)
        } finally { release.complete(Unit); session.close() }
    }

    @Test fun failureRequiresExplicitRetryAndSuccessfulRetryClearsTheOldFailureState() = runBlocking {
        var calls = 0
        val session = ProcessTextReviewSession(this) {
            calls++
            if (calls == 1) throw IOException("Owned disconnected backend")
            ProcessTextTranslationPresentation("Recovered translation", true)
        }
        try {
            session.start("Original selection", readOnly = false)
            withTimeout(2_000) { session.state.first { it?.failed == true } }
            assertEquals(1, calls)
            assertNull(session.replacement())
            session.start("Original selection", readOnly = false)
            assertEquals(1, calls)
            session.retry()
            withTimeout(2_000) { session.state.first { it?.succeeded == true } }
            assertEquals(2, calls)
            assertFalse(requireNotNull(session.state.value).failed)
            assertFalse(requireNotNull(session.state.value).interrupted)
            assertEquals("Recovered translation", session.replacement())
        } finally { session.close() }
    }

    @Test fun processRestorationNeverRepeatsPotentiallyPaidRequestWithoutExplicitRetry() = runBlocking {
        var calls = 0
        val session = ProcessTextReviewSession(this) {
            calls++
            ProcessTextTranslationPresentation("Freshly requested", true)
        }
        try {
            session.start("Restored selection", readOnly = false, translateNow = false)
            assertTrue(requireNotNull(session.state.value).interrupted)
            assertFalse(requireNotNull(session.state.value).busy)
            assertEquals(0, calls)
            assertNull(session.replacement())
            session.retry()
            withTimeout(2_000) { session.state.first { it?.succeeded == true } }
            assertEquals(1, calls)
            assertFalse(requireNotNull(session.state.value).interrupted)
            assertEquals("Freshly requested", session.replacement())
            session.retry()
            assertEquals("A ready result is not a retry request", 1, calls)
        } finally { session.close() }
    }

    @Test fun independentlyInterruptedBackendLeavesAnExplicitRetryState() = runBlocking {
        var calls = 0
        val session = ProcessTextReviewSession(this) {
            if (++calls == 1) throw CancellationException("Owned SDK interruption")
            ProcessTextTranslationPresentation("Retry result", true)
        }
        try {
            session.start("Selection", readOnly = true)
            withTimeout(2_000) { session.state.first { it?.interrupted == true } }
            assertFalse(requireNotNull(session.state.value).failed)
            session.retry()
            withTimeout(2_000) { session.state.first { it?.succeeded == true } }
            assertEquals(2, calls)
            assertEquals("Retry result", session.copyText())
            assertNull(session.replacement())
        } finally { session.close() }
    }

    @Test fun oversizeAndBlankSelectionsCannotSendSilentlyTruncatedData() = runBlocking {
        var submitted: String? = null
        val session = ProcessTextReviewSession(this) { source ->
            submitted = source
            ProcessTextTranslationPresentation("Result", true)
        }
        try {
            for (invalid in listOf(" ", "x".repeat(PROCESS_TEXT_MAX_LENGTH + 1))) {
                try { session.start(invalid, readOnly = false); fail("Invalid selection accepted") }
                catch (_: IllegalArgumentException) { }
                assertNull(submitted)
                assertNull(session.state.value)
            }
            val full = " " + "x".repeat(PROCESS_TEXT_MAX_LENGTH - 2) + " "
            session.start(full, readOnly = false)
            withTimeout(2_000) { session.state.first { it?.succeeded == true } }
            assertEquals(full, submitted)
            assertEquals(full, session.state.value?.source)
        } finally { session.close() }
    }
}
