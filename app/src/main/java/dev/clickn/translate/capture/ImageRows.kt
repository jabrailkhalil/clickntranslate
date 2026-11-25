package dev.clickn.translate.capture

import java.nio.ByteBuffer

/** Copies actual pixels from a plane whose final row has no guarantee of trailing padding. */
internal fun packImageRows(source: ByteBuffer, rowBytes: Int, rowStride: Int, height: Int): ByteBuffer {
    require(height > 0 && rowBytes > 0 && rowStride >= rowBytes)
    val required = (height - 1L) * rowStride + rowBytes
    require(required <= source.remaining()) { "Image plane ends before its last pixel" }

    val rows = source.duplicate()
    val start = rows.position()
    val packed = ByteBuffer.allocate(rowBytes * height)
    repeat(height) { y ->
        val offset = start + y * rowStride
        rows.limit(offset + rowBytes)
        rows.position(offset)
        packed.put(rows)
    }
    packed.flip()
    return packed
}
