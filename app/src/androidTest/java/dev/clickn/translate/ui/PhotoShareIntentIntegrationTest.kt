package dev.clickn.translate.ui

import android.content.ClipData
import android.content.Intent
import android.net.Uri
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class PhotoShareIntentIntegrationTest {
    private val first = Uri.parse("content://owned.test/first.png")
    private val second = Uri.parse("content://owned.test/second.png")

    @Test fun singleImageAcceptsDataAndClipFallbackButExplicitStreamHasPriority() {
        assertEquals(listOf(first.toString()), sharedGalleryImageUris(
            Intent(Intent.ACTION_SEND).setDataAndType(first, "image/png")))
        val clip = Intent(Intent.ACTION_SEND).setType("image/png").apply {
            clipData = ClipData.newRawUri("owned", second)
        }
        assertEquals(listOf(second.toString()), sharedGalleryImageUris(clip))
        clip.putExtra(Intent.EXTRA_STREAM, first)
        assertEquals(listOf(first.toString()), sharedGalleryImageUris(clip))
    }

    @Test fun multipleClipUrisKeepOrderDeduplicateAndRejectFileOrNonImagePayloads() {
        val clip = ClipData.newRawUri("owned", first).apply {
            addItem(ClipData.Item(second))
            addItem(ClipData.Item(first))
            addItem(ClipData.Item(Uri.parse("file:///data/user/0/private/image.png")))
        }
        val request = Intent(Intent.ACTION_SEND_MULTIPLE).setType("image/png").apply { clipData = clip }
        assertEquals(listOf(first.toString(), second.toString()), sharedGalleryImageUris(request))
        request.type = "text/plain"
        assertTrue(sharedGalleryImageUris(request).isEmpty())
    }
}
