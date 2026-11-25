package dev.clickn.translate.gallery

import java.io.InputStream
import java.io.OutputStream
import java.io.IOException

internal const val MAX_GALLERY_IMAGE_BYTES = 50L * 1024 * 1024
internal const val GALLERY_COPY_STORAGE_RESERVE = 64L * 1024 * 1024

/** Existing persistable inputs keep their prior >50MiB admission, bounded by real private storage. */
internal fun galleryImageCopyBudget(persistableSource: Boolean, usableSpace: Long): Long {
    if (usableSpace <= GALLERY_COPY_STORAGE_RESERVE) {
        throw IOException("Not enough free space to copy the selected image.")
    }
    val available = usableSpace - GALLERY_COPY_STORAGE_RESERVE
    return if (persistableSource) available else minOf(MAX_GALLERY_IMAGE_BYTES, available)
}

/** Bound a provider-controlled stream before it can fill the app's storage. */
internal fun copyGalleryImage(
    input: InputStream,
    output: OutputStream,
    maxBytes: Long = MAX_GALLERY_IMAGE_BYTES,
    checkpoint: () -> Unit = {},
): Long {
    require(maxBytes > 0)
    val buffer = ByteArray(16 * 1024)
    var copied = 0L
    while (true) {
        checkpoint()
        val read = input.read(buffer)
        checkpoint()
        if (read < 0) return copied
        if (read == 0) continue
        if (copied + read > maxBytes) throw IOException("Selected image exceeds the size limit")
        output.write(buffer, 0, read)
        copied += read
    }
}
