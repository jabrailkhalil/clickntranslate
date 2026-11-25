package dev.clickn.translate.gallery

import android.graphics.Bitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Recycle an unpublished decode if cancellation wins the IO-to-caller handoff. */
internal suspend fun loadGalleryBitmap(decode: suspend () -> Bitmap?): Bitmap? {
    var unpublished: Bitmap? = null
    try {
        val result = withContext(Dispatchers.IO) {
            decode().also { unpublished = it }
        }
        // A displayed bitmap belongs to Compose/rendering, not to the IO job.
        unpublished = null
        return result
    } finally {
        unpublished?.takeUnless { it.isRecycled }?.recycle()
    }
}
