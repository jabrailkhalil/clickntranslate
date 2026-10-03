package dev.clickn.translate.overlay

internal object OverlayReadingPolicy {
    /** Longer results receive more reading time; touching or pinning pauses dismissal. */
    fun delayMs(characterCount: Int): Long =
        (15_000L + characterCount.coerceAtLeast(0).toLong() * 35L).coerceAtMost(60_000L)
    fun mayDismiss(loading: Boolean, pinned: Boolean, touching: Boolean, speaking: Boolean): Boolean =
        !loading && !pinned && !touching && !speaking
}
