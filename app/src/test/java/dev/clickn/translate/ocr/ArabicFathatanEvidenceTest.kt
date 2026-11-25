package dev.clickn.translate.ocr

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ArabicFathatanEvidenceTest {
    private val width = 54
    private val height = 47

    private fun patch(offsets: List<Pair<Int, Int>>, dark: Boolean = false, contrast: Int = 220): IntArray {
        val background = if (dark) 15 else 245
        val foreground = if (dark) background + contrast else background - contrast
        fun gray(v: Int) = 0xff000000.toInt() or (v * 0x010101)
        val pixels = IntArray(width * height) { gray(background) }
        for ((x0, y0) in offsets) for (dx in 0 until 16) for (dy in 0 until 3) {
            val x = x0 + dx
            val y = y0 - dx / 3 + dy
            if (x in 0 until width && y in 0 until height) pixels[y * width + x] = gray(foreground)
        }
        return pixels
    }

    private fun has(pixels: IntArray) = ArabicFathatanEvidence.hasParallelStrokes(pixels, width, height, 84)

    @Test fun twoCompleteStrokesWorkWithEitherPolarity() {
        val pair = listOf(16 to 16, 17 to 23)
        assertTrue(has(patch(pair)))
        assertTrue(has(patch(pair, dark = true)))
    }

    @Test fun aSingleFathaAndNeighbouringOrClippedMarksAreNotNunation() {
        assertFalse(has(patch(listOf(16 to 16))))
        assertFalse(has(patch(listOf(7 to 16, 27 to 18))))
        assertFalse(has(patch(listOf(16 to 16, 17 to 23), contrast = 40)))
        assertFalse(has(patch(listOf(-2 to 16, -1 to 23))))
        assertFalse(has(patch(listOf(16 to 13, 16 to 20, 16 to 27))))
    }
}
