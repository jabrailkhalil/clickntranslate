// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import dev.clickn.translate.data.LoopTriggerMode

internal enum class LoopActiveResultDecision {
    CAPTURE,
    KEEP_TRANSLATING,
    KEEP_VISIBLE,
}

internal enum class LoopIndicatorMode {
    COUNTDOWN,
    INDETERMINATE,
}

internal data class LoopIndicatorSpec(
    val mode: LoopIndicatorMode,
    val periodMs: Long,
)

internal object LoopRuntimePolicy {
    const val SMART_INDICATOR_PERIOD_MS: Long = 1600L

    fun usesStabilityPolling(mode: LoopTriggerMode): Boolean =
        mode != LoopTriggerMode.FIXED_INTERVAL

    fun pollingIntervalMs(
        configuredLoopIntervalMs: Long,
        mode: LoopTriggerMode,
        backendMinimumMs: Long,
        sourceResultPresent: Boolean = false,
    ): Long = maxOf(
        LoopFrameStabilityPolicy.pollingIntervalMs(
            configuredLoopIntervalMs = configuredLoopIntervalMs,
            enabled = usesStabilityPolling(mode),
        ),
        backendMinimumMs.coerceAtLeast(0L),
        // Text-completion probes can be fast while the first text is appearing. Once a page
        // has been processed, avoid hiding/redrawing its translation five times a second.
        if (sourceResultPresent && usesStabilityPolling(mode)) 1_500L else 0L,
    )

    fun activeResultDecision(
        hasBlockingResult: Boolean,
        translationInFlight: Boolean,
        canCaptureCleanSource: Boolean = false,
    ): LoopActiveResultDecision {
        if (translationInFlight) return LoopActiveResultDecision.KEEP_TRANSLATING
        if (!hasBlockingResult || canCaptureCleanSource) return LoopActiveResultDecision.CAPTURE
        return LoopActiveResultDecision.KEEP_VISIBLE
    }

    /** Interval/text modes tolerate animated backgrounds while their recognized source stays stable. */
    fun sameSourceDuringTranslation(
        mode: LoopTriggerMode,
        sameFrame: Boolean,
        sameText: Boolean?,
    ): Boolean = if (mode != LoopTriggerMode.SETTLED_PAGE && sameText != null) {
        sameText
    } else {
        sameFrame && sameText != false
    }

    fun indicatorSpec(
        configuredLoopIntervalMs: Long,
        smartMode: Boolean,
    ): LoopIndicatorSpec = if (smartMode) {
        LoopIndicatorSpec(
            mode = LoopIndicatorMode.INDETERMINATE,
            periodMs = SMART_INDICATOR_PERIOD_MS,
        )
    } else {
        LoopIndicatorSpec(
            mode = LoopIndicatorMode.COUNTDOWN,
            periodMs = configuredLoopIntervalMs.takeIf { it > 0L }
                ?: LoopFrameStabilityPolicy.DEFAULT_LOOP_INTERVAL_MS,
        )
    }
}
