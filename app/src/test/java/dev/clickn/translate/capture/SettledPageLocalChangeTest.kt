package dev.clickn.translate.capture

import kotlin.math.abs
import org.junit.Assert.*
import org.junit.Test

class SettledPageLocalChangeTest {
    private val threshold = LoopFrameChangePolicy.DEFAULT_SIMILARITY_THRESHOLD

    @Test fun smallParagraphChangeIsNotDilutedByAWhiteFullPage() {
        val before = paragraph(shift = 0)
        val after = paragraph(shift = 1)
        assertTrue("The old whole-page mean misses this sparse text change", globalSimilarity(before, after) > threshold)
        assertTrue(requireNotNull(SettledPageVisualPolicy.similarity(before, after)) < threshold)
        assertEquals(1f, requireNotNull(SettledPageVisualPolicy.similarity(before, before)), 0f)
    }

    @Test fun clockBlinkAndDisconnectedNoiseDoNotBecomeAPageTurn() {
        val original = paragraph(shift = 0)
        val cases = listOf(
            "one blinking pixel" to original.luminance.copyOf().apply { this[4] = 0 },
            "one clock tile" to paintedTiles(original.luminance, listOf(2 to 0), 0),
            "two clock tiles" to paintedTiles(original.luminance, listOf(2 to 0, 3 to 0), 0),
            "three disconnected blinks" to paintedTiles(original.luminance, listOf(1 to 1, 6 to 1, 10 to 1), 0),
            "small low contrast noise" to paintedTiles(original.luminance, listOf(1 to 1, 2 to 1, 3 to 1), 252),
        )
        for ((name, pixels) in cases) {
            val noisy = original.copy(luminance = pixels)
            assertTrue(name, requireNotNull(SettledPageVisualPolicy.similarity(original, noisy)) >= threshold)
        }
    }

    @Test fun movingAndDismissedOwnOverlaysDoNotHideTheNextRealParagraphChange() {
        val original = paragraph(shift = 0)
        val changed = paragraph(shift = 1)
        val oldBounds = OverlayCaptureRect(8, 8, 44, 28)
        val newBounds = OverlayCaptureRect(42, 10, 78, 30)
        val oldOverlay = withOverlay(original, oldBounds, 0)
        val movedOverlay = withOverlay(original, newBounds, 224)
        assertEquals(1f, requireNotNull(SettledPageVisualPolicy.similarity(original, oldOverlay)), 0f)
        assertEquals(1f, requireNotNull(SettledPageVisualPolicy.similarity(oldOverlay, movedOverlay)), 0f)
        assertEquals(1f, requireNotNull(SettledPageVisualPolicy.similarity(movedOverlay, original)), 0f)
        assertTrue(requireNotNull(SettledPageVisualPolicy.similarity(oldOverlay,
            withOverlay(changed, newBounds, 224))) < threshold)
    }

    @Test fun narrowCommonSliversCannotPromoteThreeNoisyTiles() {
        val before = frame(ByteArray(SIDE * SIDE) { 255.toByte() }).copy(
            visible = BooleanArray(SIDE * SIDE) { (it / SIDE) % TILE < 4 },
        )
        // Half the source remains common overall, but each tile has only 50% common coverage.
        val after = before.copy(luminance = paintedTiles(before.luminance, listOf(1 to 5, 2 to 5, 3 to 5), 0))
        assertTrue(globalSimilarity(before, after) > threshold)
        assertTrue(requireNotNull(SettledPageVisualPolicy.similarity(before, after)) >= threshold)
    }

    @Test fun supportedContrastUsesTheExistingMonotonicThresholdMeaning() {
        val before = frame(ByteArray(SIDE * SIDE) { 255.toByte() })
        val after = before.copy(luminance = paintedTiles(before.luminance, listOf(1 to 5, 2 to 5, 3 to 5), 239))
        val similarity = requireNotNull(SettledPageVisualPolicy.similarity(before, after))
        assertEquals(239f / 255f, similarity, 0.000001f)
        assertTrue("Less sensitive 90% keeps this contrast", similarity >= .90f)
        assertTrue("Default 95% notices the same contrast", similarity < .95f)
        val decisions = listOf(.50f, .90f, .95f, .99f).map { similarity < it }
        assertEquals(listOf(false, false, true, true), decisions)
    }

    @Test fun submittedPageDismissalThenChangedParagraphSettlesAndSubmitsWithoutReset() {
        val pageA = paragraph(shift = 0)
        val pageB = paragraph(shift = 1)
        val policy = SettledPagePolicy()
        var anchor: SettledPageFrame? = null
        fun observe(frame: SettledPageFrame, now: Long): SettledPagePolicy.Decision {
            val same = anchor?.let { requireNotNull(SettledPageVisualPolicy.similarity(it, frame)) >= threshold } ?: false
            return policy.observe(same, true, now, 500L).also { if (it.replaceAnchor) anchor = frame }
        }
        assertFalse(observe(pageA, 0).ready)
        val first = observe(pageA, 500)
        assertTrue(first.ready)
        assertTrue(policy.claim(first.revision))
        // Dismissing a result leaves the same source page; it must not cause another request.
        assertFalse(observe(pageA, 1000).ready)
        assertFalse(policy.claim(first.revision))
        val changed = observe(pageB, 1100)
        assertTrue(changed.invalidatePrevious)
        assertTrue(changed.replaceAnchor)
        assertFalse(changed.ready)
        assertFalse("Late MT from the old paragraph must be rejected", policy.accepts(first.revision))
        assertFalse(observe(pageB, 1599).ready)
        val second = observe(pageB, 1600)
        assertTrue(second.ready)
        assertTrue(policy.claim(second.revision))
        assertTrue(second.revision > first.revision)
        assertFalse(observe(pageB, 2100).ready)
        assertFalse(policy.claim(second.revision))
    }

    private fun paragraph(shift: Int): SettledPageFrame {
        val pixels = ByteArray(SIDE * SIDE) { 255.toByte() }
        // Three short lines of dark glyph strokes occupy a small part of a white page.
        for (line in 0..2) for (glyph in 0..9) {
            val x = 8 + glyph * 7 + shift
            val y = 43 + line * 4
            for (dy in 0..2) pixels[(y + dy) * SIDE + x] = 0
            for (dx in 0..2) {
                pixels[y * SIDE + x + dx] = 0
                pixels[(y + 2) * SIDE + x + dx] = 0
            }
        }
        return frame(pixels)
    }

    private fun frame(pixels: ByteArray) = SettledPageFrame(SIDE, SIDE, 1, pixels, BooleanArray(pixels.size) { true })

    private fun paintedTiles(source: ByteArray, tiles: List<Pair<Int, Int>>, value: Int): ByteArray =
        source.copyOf().apply {
            for ((tx, ty) in tiles) for (y in ty * TILE until (ty + 1) * TILE) {
                for (x in tx * TILE until (tx + 1) * TILE) this[y * SIDE + x] = value.toByte()
            }
        }

    private fun withOverlay(source: SettledPageFrame, bounds: OverlayCaptureRect, color: Int): SettledPageFrame {
        val pixels = source.luminance.copyOf()
        for (y in bounds.top until bounds.bottom) for (x in bounds.left until bounds.right) pixels[y * SIDE + x] = color.toByte()
        return source.copy(luminance = pixels,
            visible = SettledPageVisualPolicy.visibility(SIDE, SIDE, SIDE, listOf(bounds)))
    }

    private fun globalSimilarity(a: SettledPageFrame, b: SettledPageFrame): Float {
        var difference = 0L
        var count = 0
        for (i in a.luminance.indices) if (a.visible[i] && b.visible[i]) {
            count++
            difference += abs((a.luminance[i].toInt() and 255) - (b.luminance[i].toInt() and 255))
        }
        return (1.0 - difference.toDouble() / (count.toLong() * 255L)).toFloat()
    }

    private companion object {
        const val SIDE = 96
        const val TILE = 8
    }
}
