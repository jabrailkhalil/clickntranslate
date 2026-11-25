// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

/**
 * Pure scheduling policy for page observation, independent of capture/OCR/translation jobs.
 * The visual comparator must compare against the candidate anchor,
 * not merely the preceding frame, so slow scrolling cannot accumulate unnoticed drift.
 * Null/obscured/failed observations must not be submitted as "unchanged" frames.
 */
internal class SettledPagePolicy {
    data class Decision(
        val revision: Long,
        val invalidatePrevious: Boolean,
        val replaceAnchor: Boolean,
        val ready: Boolean,
    )

    /** Identifies one execution, including retries of the same page revision. */
    data class AttemptTicket(val revision: Long, val attemptId: Long)

    private var revision = 0L
    private var hasAnchor = false
    private var stableSinceMs = 0L
    private var lastObservationMs: Long? = null
    private var submittedRevision: Long? = null
    private var readyRevision: Long? = null
    private var observationPaused = false
    private var attemptSequence = 0L
    private var activeAttempt: AttemptTicket? = null
    private var retryNotBeforeMs: Long? = null
    private var consecutiveFailures = 0

    @Synchronized
    fun observe(
        sameAsAnchor: Boolean,
        contextUnchanged: Boolean,
        nowMs: Long,
        stableDurationMs: Long,
    ): Decision {
        val clockWentBack = lastObservationMs?.let { nowMs < it } == true
        lastObservationMs = nowMs
        val changed = !hasAnchor || !contextUnchanged || !sameAsAnchor || clockWentBack
        if (observationPaused) stableSinceMs = nowMs
        observationPaused = false
        if (changed) {
            val invalidate = hasAnchor
            revision++
            hasAnchor = true
            stableSinceMs = nowMs
            submittedRevision = null
            readyRevision = null
            clearRetryState()
            return Decision(revision, invalidate, replaceAnchor = true, ready = false)
        }
        val ready = submittedRevision != revision &&
            nowMs - stableSinceMs >= stableDurationMs.coerceAtLeast(1L) &&
            (retryNotBeforeMs?.let { nowMs >= it } != false)
        readyRevision = revision.takeIf { ready }
        return Decision(
            revision,
            invalidatePrevious = false,
            replaceAnchor = false,
            ready = ready,
        )
    }

    /** Claim only after an execution slot is available; never queue intermediate pages. */
    @Synchronized
    fun claim(expectedRevision: Long): Boolean = claimAttempt(expectedRevision) != null

    @Synchronized
    fun claimAttempt(expectedRevision: Long): AttemptTicket? {
        if (!hasAnchor || expectedRevision != revision || readyRevision != revision || submittedRevision == revision) return null
        submittedRevision = revision
        retryNotBeforeMs = null
        return AttemptTicket(revision, ++attemptSequence).also { activeAttempt = it }
    }

    /**
     * Only a caller-classified transient failure permits another execution of this page.
     * Empty/successful pages remain submitted. A late callback from an earlier attempt cannot
     * reopen a revision currently being processed by its retry.
     */
    @Synchronized
    fun retryAfterFailure(ticket: AttemptTicket, nowMs: Long): Boolean {
        if (!hasAnchor || ticket != activeAttempt || ticket.revision != revision || submittedRevision != revision) return false
        // Leave a backwards timestamp for observe() to handle as a page discontinuity.
        if (lastObservationMs?.let { nowMs < it } == true) return false
        val failures = (consecutiveFailures + 1).coerceAtMost(6)
        val delayMs = when (failures) {
            1 -> 1_000L
            2 -> 2_000L
            3 -> 4_000L
            4 -> 8_000L
            5 -> 16_000L
            else -> 30_000L
        }
        // An unrepresentable future deadline must not become an immediate retry loop.
        if (nowMs > Long.MAX_VALUE - delayMs) return false
        consecutiveFailures = failures
        lastObservationMs = nowMs
        retryNotBeforeMs = nowMs + delayMs
        activeAttempt = null
        submittedRevision = null
        readyRevision = null
        return true
    }

    @Synchronized
    fun accepts(expectedRevision: Long): Boolean = hasAnchor && expectedRevision == revision

    /** Occlusion is not a page turn. Preserve the displayed/submitted page but restart settling. */
    @Synchronized
    fun pauseObservation(nowMs: Long) {
        observationPaused = true
        stableSinceMs = nowMs
        lastObservationMs = nowMs
        readyRevision = null
    }

    /** A discontinuity (sleep, lost capture session, stopped loop) invalidates pending results. */
    @Synchronized
    fun reset() {
        revision++
        hasAnchor = false
        stableSinceMs = 0L
        lastObservationMs = null
        submittedRevision = null
        readyRevision = null
        observationPaused = false
        clearRetryState()
    }

    private fun clearRetryState() {
        activeAttempt = null
        retryNotBeforeMs = null
        consecutiveFailures = 0
    }
}
