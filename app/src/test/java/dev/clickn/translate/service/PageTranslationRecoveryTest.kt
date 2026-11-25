package dev.clickn.translate.service

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.currentTime
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class PageTranslationRecoveryTest {
    @Test fun offlinePageRecoversWithoutRepeatingSuccessfulUnitsOrRecognition() = runTest {
        val attempts = mutableListOf<List<Int>>()
        val retryTimes = mutableListOf<Long>()
        val result = recoverPageTranslations(3, mapOf(0 to "cached"), true, {},
            onRetry = { _, _ -> retryTimes += currentTime },
        ) { indexes, accept ->
            attempts += indexes
            when (attempts.size) {
                1 -> accept(1, "first")
                3 -> accept(2, "recovered")
            }
        }
        assertEquals(listOf(listOf(1, 2), listOf(2), listOf(2)), attempts)
        assertEquals(listOf(0L, 2_000L), retryTimes)
        assertEquals(6_000L, currentTime)
        assertEquals(mapOf(0 to "cached", 1 to "first", 2 to "recovered"), result)
    }

    @Test fun disabledRetryRetainsPartialSuccessAndDoesNotRepeatRequests() = runTest {
        var calls = 0
        val result = recoverPageTranslations(2, emptyMap(), false, {}) { _, accept ->
            calls++
            accept(0, "translated")
            accept(1, " ")
        }
        assertEquals(1, calls)
        assertEquals(0L, currentTime)
        assertEquals(mapOf(0 to "translated"), result)
    }

    @Test fun persistentFailureIsBoundedAndStoppingCancelsTheWaitingRequest() = runTest {
        val times = mutableListOf<Long>()
        val job = async {
            recoverPageTranslations(1, emptyMap(), true, {}) { _, _ -> times += currentTime }
        }
        runCurrent()
        advanceTimeBy(90_001)
        runCurrent()
        assertEquals(listOf(0L, 2_000L, 6_000L, 14_000L, 30_000L, 60_000L, 90_000L), times)
        job.cancelAndJoin()
        advanceTimeBy(60_000)
        assertEquals(7, times.size)
    }

    @Test fun changedPageRejectsTheLateResponseAndNeverSchedulesItsRetry() = runTest {
        var current = true
        var retries = 0
        try {
            recoverPageTranslations(1, emptyMap(), true,
                ensureCurrent = { if (!current) throw CancellationException("Page changed") },
                onRetry = { _, _ -> retries++ },
            ) { _, accept ->
                current = false
                accept(0, "old page")
            }
            fail("Old page response accepted")
        } catch (_: CancellationException) {
            assertEquals(0, retries)
        }
    }

    @Test fun successfulAndEmptyPagesDoNotStartMoreWork() = runTest {
        for ((count, existing) in listOf(0 to emptyMap<Int, String>(), 1 to mapOf(0 to "ready"))) {
            val result = recoverPageTranslations(count, existing, true, {}) { _, _ ->
                fail("Already completed page was submitted")
            }
            assertEquals(existing, result)
        }
    }

    @Test fun indivisiblePageRequestRecoversWithBoundedBackoffAndReturnsItsActualResult() = runTest {
        val attempts = mutableListOf<Long>()
        val delays = mutableListOf<Long>()
        val expected = listOf("first translated block", "second translated block")
        val failure = IOException("Temporarily offline")
        val result = retryCurrentPageRequest(true, {}, onRetry = { error, delayMs ->
            assertSame(failure, error)
            delays += delayMs
        }) {
            attempts += currentTime
            if (attempts.size < 7) throw failure
            expected
        }
        assertSame(expected, result)
        assertEquals(listOf(0L, 2_000L, 6_000L, 14_000L, 30_000L, 60_000L, 90_000L), attempts)
        assertEquals(listOf(2_000L, 4_000L, 8_000L, 16_000L, 30_000L, 30_000L), delays)
    }

    @Test fun cancellingAnIndivisibleRequestDuringBackoffPreventsFurtherNetworkWork() = runTest {
        var requests = 0
        val job = async {
            retryCurrentPageRequest<Nothing>(true, {}) {
                requests++
                throw IOException("Offline")
            }
        }
        runCurrent()
        assertEquals(1, requests)
        job.cancelAndJoin()
        advanceTimeBy(60_000L)
        runCurrent()
        assertEquals(1, requests)
    }

    @Test fun indivisibleRequestDoesNotRetryCancellationOrFatalErrors() = runTest {
        for (failure in listOf(CancellationException("Stopped"), AssertionError("Fatal failure"))) {
            var requests = 0
            try {
                retryCurrentPageRequest<Nothing>(true, {}, onRetry = { _, _ ->
                    fail("Cancellation and fatal errors must never schedule a retry")
                }) {
                    requests++
                    throw failure
                }
            } catch (actual: Throwable) {
                assertSame(failure, actual)
            }
            assertEquals(1, requests)
            assertEquals(0L, currentTime)
        }
    }

    @Test fun disabledIndivisibleRequestRetryThrowsTheOriginalExceptionImmediately() = runTest {
        val failure = IOException("Offline")
        var requests = 0
        try {
            retryCurrentPageRequest<Nothing>(false, {}, onRetry = { _, _ ->
                fail("Disabled retry must not schedule a delay")
            }) {
                requests++
                throw failure
            }
        } catch (actual: IOException) {
            assertSame(failure, actual)
        }
        assertEquals(1, requests)
        assertEquals(0L, currentTime)
    }

    @Test fun pageChangeRejectsAnIndivisibleResponseBeforeReturningOrSchedulingRetry() = runTest {
        var current = true
        try {
            retryCurrentPageRequest(true,
                ensureCurrent = { if (!current) throw CancellationException("Page changed") },
                onRetry = { _, _ -> fail("A stale response cannot schedule a retry") },
            ) {
                kotlinx.coroutines.delay(10L)
                current = false
                "late response"
            }
            fail("A stale response was returned")
        } catch (_: CancellationException) {
            assertEquals(10L, currentTime)
        }
    }

    @Test fun pageChangeDuringBackoffRejectsTheNextIndivisibleRequest() = runTest {
        var current = true
        var requests = 0
        val job = async {
            retryCurrentPageRequest<Nothing>(true,
                ensureCurrent = { if (!current) throw CancellationException("Page changed") },
            ) {
                requests++
                throw IOException("Offline")
            }
        }
        runCurrent()
        advanceTimeBy(1_000L)
        current = false
        advanceTimeBy(1_001L)
        runCurrent()
        try {
            job.await()
            fail("A page change must cancel the waiting request")
        } catch (_: CancellationException) {
            assertEquals(1, requests)
        }
    }
}
