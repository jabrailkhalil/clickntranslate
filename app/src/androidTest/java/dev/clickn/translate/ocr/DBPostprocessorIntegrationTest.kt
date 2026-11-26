package dev.clickn.translate.ocr

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class DBPostprocessorIntegrationTest {
    @Test fun diagonalTouchAtTheFrameEdgeJoinsOnlyTheTwoTouchingComponents() {
        val map = Array(18) { FloatArray(28) }
        for (y in 0..5) for (x in 0..5) map[y][x] = 1f
        for (y in 6..11) for (x in 6..11) map[y][x] = 1f
        for (y in 4..14) for (x in 18..25) map[y][x] = 1f
        val boxes = DBPostprocessor.extractQuads(map, 1f, 1f, .5f, .1f, 0f)
        assertEquals(2, boxes.size)
        assertEquals(listOf(18, 4, 25, 14), boxes.last().axisAlignedBounds().toList())
    }

    @Test fun hollowBoxScoreIncludesOnlyPixelCentersInsideItsHull() {
        val map = Array(14) { y -> FloatArray(14) { x ->
            if (x in 2..10 && y in 2..10 && (x == 2 || x == 10 || y == 2 || y == 10)) 1f else 0f
        } }
        // The hull contains an 8x8 grid of pixel centers, 15 of them on the ring.
        val score = 15f / 64f
        assertEquals(1, DBPostprocessor.extractQuads(map, 1f, 1f, .5f, score, 0f).size)
        assertEquals(0, DBPostprocessor.extractQuads(map, 1f, 1f, .5f, score + .0001f, 0f).size)
    }
}
