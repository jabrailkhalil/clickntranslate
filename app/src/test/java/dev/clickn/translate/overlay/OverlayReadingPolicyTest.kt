package dev.clickn.translate.overlay

import org.junit.Assert.*
import org.junit.Test

class OverlayReadingPolicyTest {
    @Test fun readingTimeIsBoundedAndIncreasesForLongResults() {
        assertEquals(15_000L, OverlayReadingPolicy.delayMs(0))
        assertTrue(OverlayReadingPolicy.delayMs(400) > OverlayReadingPolicy.delayMs(40))
        assertEquals(60_000L, OverlayReadingPolicy.delayMs(Int.MAX_VALUE))
        assertEquals(15_000L, OverlayReadingPolicy.delayMs(-10))
    }
    @Test fun loadingPinTouchAndSpeechAllPreventAutomaticDismissal() {
        assertTrue(OverlayReadingPolicy.mayDismiss(false, false, false, false))
        assertFalse(OverlayReadingPolicy.mayDismiss(true, false, false, false))
        assertFalse(OverlayReadingPolicy.mayDismiss(false, true, false, false))
        assertFalse(OverlayReadingPolicy.mayDismiss(false, false, true, false))
        assertFalse(OverlayReadingPolicy.mayDismiss(false, false, false, true))
    }
}
