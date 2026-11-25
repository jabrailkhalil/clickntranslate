package dev.clickn.translate.capture

import org.junit.Assert.*
import org.junit.Test

class SettledPageRetryPolicyTest {
    @Test fun onlyAnExplicitFailureCanRetryTheStablePageAndMustWaitTheBackoff() {
        val policy = SettledPagePolicy()
        val revision = readyPage(policy)
        val first = requireNotNull(policy.claimAttempt(revision))
        assertFalse(policy.observe(true, true, 150, 100).ready)
        assertTrue(policy.retryAfterFailure(first, 200))
        assertFalse(policy.observe(true, true, 1199, 100).ready)
        assertNull(policy.claimAttempt(revision))
        assertTrue(policy.observe(true, true, 1200, 100).ready)
        val retry = requireNotNull(policy.claimAttempt(revision))
        assertEquals(first.revision, retry.revision)
        assertTrue(retry.attemptId > first.attemptId)
        assertFalse("A completed/empty page is not automatically retried", policy.observe(true, true, 60_000, 100).ready)
    }

    @Test fun repeatedTransientFailuresBackOffToThirtySecondsWithoutStoppingOfflineRecovery() {
        val policy = SettledPagePolicy()
        val revision = readyPage(policy)
        var ticket = requireNotNull(policy.claimAttempt(revision))
        var now = 150L
        for (delay in listOf(1000L, 2000L, 4000L, 8000L, 16_000L, 30_000L, 30_000L, 30_000L)) {
            assertTrue(policy.retryAfterFailure(ticket, now))
            assertFalse("Must not poll retry before $delay ms", policy.observe(true, true, now + delay - 1, 100).ready)
            assertNull(policy.claimAttempt(revision))
            now += delay
            assertTrue(policy.observe(true, true, now, 100).ready)
            ticket = requireNotNull(policy.claimAttempt(revision))
            now += 10
        }
    }

    @Test fun duplicateAndLateCallbacksCannotDelayOrReopenAnotherAttempt() {
        val policy = SettledPagePolicy()
        val revision = readyPage(policy)
        val first = requireNotNull(policy.claimAttempt(revision))
        assertTrue(policy.retryAfterFailure(first, 200))
        assertFalse(policy.retryAfterFailure(first, 900))
        assertTrue(policy.observe(true, true, 1200, 100).ready)
        val second = requireNotNull(policy.claimAttempt(revision))
        assertFalse(policy.retryAfterFailure(first, 1300))
        assertTrue(policy.retryAfterFailure(second, 1400))
        assertFalse(policy.retryAfterFailure(second, 3000))
        assertFalse(policy.observe(true, true, 3399, 100).ready)
        assertTrue(policy.observe(true, true, 3400, 100).ready)
    }

    @Test fun pageContextClockAndResetDiscardOldTicketsAndTheirFailureBudget() {
        for (discontinuity in listOf("page", "context", "clock", "reset")) {
            val policy = SettledPagePolicy()
            val firstPage = policy.observe(false, true, 1000, 100)
            assertTrue(policy.observe(true, true, 1100, 100).ready)
            val old = requireNotNull(policy.claimAttempt(firstPage.revision))
            assertTrue(policy.retryAfterFailure(old, 1200))
            val changedAt = if (discontinuity == "clock") 900L else 1300L
            if (discontinuity == "reset") policy.reset()
            val changed = policy.observe(
                sameAsAnchor = discontinuity != "page",
                contextUnchanged = discontinuity != "context",
                nowMs = changedAt,
                stableDurationMs = 100,
            )
            assertFalse(discontinuity, policy.accepts(old.revision))
            assertFalse(discontinuity, policy.retryAfterFailure(old, changedAt))
            assertFalse(changed.ready)
            assertTrue(policy.observe(true, true, changedAt + 100, 100).ready)
            val next = requireNotNull(policy.claimAttempt(changed.revision))
            assertTrue(next.attemptId > old.attemptId)
            assertTrue(policy.retryAfterFailure(next, changedAt + 150))
            assertFalse(policy.observe(true, true, changedAt + 1149, 100).ready)
            assertTrue("New page starts with the first 1s delay", policy.observe(true, true, changedAt + 1150, 100).ready)
        }
    }

    @Test fun aClockRollbackAfterFailureCallbackDiscardsItsFutureRetryDeadline() {
        val policy = SettledPagePolicy()
        val revision = readyPage(policy)
        val ticket = requireNotNull(policy.claimAttempt(revision))
        assertTrue(policy.retryAfterFailure(ticket, 500))
        val rolledBack = policy.observe(true, true, 300, 100)
        assertTrue(rolledBack.invalidatePrevious)
        assertTrue(rolledBack.replaceAnchor)
        assertFalse(policy.accepts(revision))
        assertFalse(rolledBack.ready)
        assertTrue(policy.observe(true, true, 400, 100).ready)
        assertNotNull(policy.claimAttempt(rolledBack.revision))
    }

    @Test fun occludedTimeDoesNotSatisfyStabilityEvenAfterRetryDeadlinePassed() {
        val policy = SettledPagePolicy()
        val revision = readyPage(policy)
        val ticket = requireNotNull(policy.claimAttempt(revision))
        assertTrue(policy.retryAfterFailure(ticket, 200))
        policy.pauseObservation(400)
        assertFalse(policy.observe(true, true, 5000, 100).ready)
        assertNull(policy.claimAttempt(revision))
        assertTrue(policy.observe(true, true, 5100, 100).ready)
        assertNotNull(policy.claimAttempt(revision))
    }

    private fun readyPage(policy: SettledPagePolicy): Long {
        val page = policy.observe(false, true, 0, 100)
        assertTrue(policy.observe(true, true, 100, 100).ready)
        return page.revision
    }
}
