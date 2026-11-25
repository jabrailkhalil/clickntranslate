package dev.clickn.translate.service

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CaptureForegroundStartTest {
    @Test fun immediatelyPromotedServiceOpensCaptureBeforeReturning() = runTest {
        val events = mutableListOf<String>()
        CaptureForegroundStart(this).start({ events += "foreground" }, { events += "projection" }, { throw it })
        assertEquals(listOf("foreground", "projection"), events)
        advanceUntilIdle()
        assertEquals(2, events.size)
    }

    @Test fun aDelayedGrantPromotesOnlyTwiceAndOpensExactlyOneProjection() = runTest {
        var attempts = 0
        var opened = 0
        CaptureForegroundStart(this).start(
            { if (++attempts == 1) throw SecurityException() },
            { opened++ }, { throw it },
        )
        advanceTimeBy(199)
        assertEquals(1, attempts)
        assertEquals(0, opened)
        advanceUntilIdle()
        assertEquals(2, attempts)
        assertEquals(1, opened)
    }

    @Test fun aReplacementStartNeverRunsTheRetryOrTheFailureOfThePreviousStart() = runTest {
        val owner = CaptureForegroundStart(this)
        val attempts = mutableListOf<String>()
        val opened = mutableListOf<String>()
        var failures = 0
        owner.start({ attempts += "old"; throw SecurityException() }, { opened += "old" }, { failures++ })
        advanceTimeBy(100)
        owner.start({ attempts += "new" }, { opened += "new" }, { failures++ })
        advanceUntilIdle()
        assertEquals(listOf("old", "new"), attempts)
        assertEquals(listOf("new"), opened)
        assertEquals(0, failures)
    }

    @Test fun stoppingPendingConsentAlsoAllowsTheNextRequestToStartNormally() = runTest {
        val owner = CaptureForegroundStart(this)
        var deniedAttempts = 0
        var opened = 0
        owner.start({ deniedAttempts++; throw SecurityException() }, { fail("Stopped capture opened") }, { throw it })
        advanceTimeBy(100)
        owner.cancel()
        advanceUntilIdle()
        assertEquals(1, deniedAttempts)
        owner.start({}, { opened++ }, { throw it })
        assertEquals(1, opened)
    }

    @Test fun denialOfTheRetryDoesNotOpenCaptureOrRetryAgain() = runTest {
        val errors = mutableListOf<Exception>()
        var attempts = 0
        val denial = SecurityException()
        CaptureForegroundStart(this).start(
            { attempts++; throw denial }, { fail("Denied capture opened") }, { errors.add(it) },
        )
        advanceUntilIdle()
        assertEquals(2, attempts)
        assertEquals(listOf(denial), errors)
    }

    @Test fun aPlatformSetupErrorAfterTheRetryReachesTheOwnersCleanup() = runTest {
        var attempts = 0
        val failure = IllegalStateException("VirtualDisplay unavailable")
        val errors = mutableListOf<Exception>()
        CaptureForegroundStart(this).start({ if (++attempts == 1) throw SecurityException() },
            { throw failure }, { errors.add(it) })
        advanceUntilIdle()
        assertEquals(listOf(failure), errors)
        assertEquals(2, attempts)
    }
}
