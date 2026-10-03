package dev.clickn.translate.gallery

import java.io.InputStream
import java.io.OutputStream
import java.io.IOException

internal const val MAX_GALLERY_IMAGE_BYTES = 50L * 1024 * 1024

/** Bound a provider-controlled stream before it can fill the app's storage. */
internal fun copyGalleryImage(input: InputStream, output: OutputStream, maxBytes: Long = MAX_GALLERY_IMAGE_BYTES): Long {
    require(maxBytes > 0)
    val buffer = ByteArray(16 * 1024)
    var copied = 0L
    while (true) {
        val read = input.read(buffer)
        if (read < 0) return copied
        if (read == 0) continue
        if (copied + read > maxBytes) throw IOException("Selected image exceeds the size limit")
        output.write(buffer, 0, read)
        copied += read
    }
}
