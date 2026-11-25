package dev.clickn.translate.capture

import org.junit.Assert.*
import org.junit.Test

class SettledTextWatchRegionsTest {
    @Test fun clippingAndDeduplicationKeepOnlyVisibleValidTextCoverage() {
        val result = SettledTextWatchRegions.bound(100, 80, listOf(
            LoopTextRect(-20, -30, 50, 40), LoopTextRect(0, 0, 50, 40),
            LoopTextRect(90, 70, 120, 100), LoopTextRect(110, 0, 120, 10),
            LoopTextRect(40, 20, 30, 30), LoopTextRect(0, 0, 0, 10),
        ))
        assertEquals(listOf(LoopTextRect(0, 0, 50, 40), LoopTextRect(90, 70, 100, 80)), result)
        assertTrue(SettledTextWatchRegions.bound(0, 80, result).isEmpty())
    }

    @Test fun manyTextAreasRemainCoveredWithinAConstantRegionAndPixelBudget() {
        val source = (0 until 200).map { index ->
            val left = index % 20 * 10
            val top = index / 20 * 10
            LoopTextRect(left, top, left + 8, top + 8)
        }
        val bounded = SettledTextWatchRegions.bound(200, 100, source)
        assertTrue(bounded.size <= 64)
        assertTrue(bounded.sumOf { it.width.toLong() * it.height } <= 200L * 100 * 2)
        source.forEach { rect ->
            assertTrue("Overflow regions must not silently disappear: $rect", bounded.any { it.contains(rect) })
        }
    }

    @Test fun overlappingLargeAreasCannotCauseUnboundedResamplingWork() {
        val source = (0 until 300).map { inset -> LoopTextRect(0, 0, 1000 - inset, 1000) }
        val bounded = SettledTextWatchRegions.bound(1000, 1000, source)
        assertTrue(bounded.size <= 64)
        assertTrue(bounded.sumOf { it.width.toLong() * it.height } <= 2_000_000)
        source.forEach { rect -> assertTrue(bounded.any { it.contains(rect) }) }
    }

    private fun LoopTextRect.contains(other: LoopTextRect) =
        left <= other.left && top <= other.top && right >= other.right && bottom >= other.bottom
}
