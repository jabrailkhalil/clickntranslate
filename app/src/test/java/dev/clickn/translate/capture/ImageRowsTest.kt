package dev.clickn.translate.capture

import java.nio.ByteBuffer
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class ImageRowsTest {
    @Test fun paddedPlaneEndingAtItsLastPixelPreservesAllRowsAndSourceBounds() {
        val source = ByteBuffer.allocateDirect(32)
        repeat(32) { source.put(it.toByte()) }
        source.position(3)
        source.limit(31)
        val packed = packImageRows(source, rowBytes = 12, rowStride = 16, height = 2)
        val result = ByteArray(packed.remaining()).also { packed.get(it) }
        assertArrayEquals(((3..14) + (19..30)).map(Int::toByte).toByteArray(), result)
        assertEquals(3, source.position())
        assertEquals(31, source.limit())
    }

    @Test fun singleRowNeedsOnlyItsPixelBytesRegardlessOfStride() {
        val pixel = byteArrayOf(0x12, 0x34, 0x56, 0x78)
        val packed = packImageRows(ByteBuffer.wrap(pixel), rowBytes = 4, rowStride = 64, height = 1)
        assertArrayEquals(pixel, ByteArray(4).also { packed.get(it) })
    }

    @Test fun genuinelyMissingPixelsAreRejectedBeforeAllocatingTheBitmap() {
        assertThrows(IllegalArgumentException::class.java) {
            packImageRows(ByteBuffer.allocate(27), rowBytes = 12, rowStride = 16, height = 2)
        }
    }
}
