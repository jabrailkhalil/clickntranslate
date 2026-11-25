package dev.clickn.translate.capture

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Rect
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.security.MessageDigest
import kotlin.math.abs
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Exact owned OtherUidTouchActivity captures from the b729 diagnostic, not user/desktop images.
 * Exercises the platform Bitmap/Skia sampler; no OCR, translator, UI injection or network is used.
 */
@RunWith(AndroidJUnit4::class)
class SettledPageParagraphBitmapIntegrationTest {
    @Test fun actualBitmapFactoryDetectsTheChangedParagraphDespiteAWhiteFullPage() {
        val before = ownedBitmap("10-loop-first-result.png",
            "c8fff4859064e3de8fb8d8369f9feed9d41cff6a28d29626e87f4252e3b466c2")
        try {
            val after = ownedBitmap("14-loop-after-change.png",
                "51cc6e90d53c61f650621477d536063b45901c212fccd46cb2b2fa6251d30a23")
            try {
                assertEquals(1080, before.width)
                assertEquals(2400, before.height)
                assertEquals(before.width, after.width)
                assertEquals(before.height, after.height)
                // Exclude the system sharing clock and our companion, leaving the source text.
                // The factory additionally guards sample cells around these physical bounds.
                val masks = listOf(Rect(0, 0, before.width, 128), Rect(0, 700, 160, 900))
                val oldPage = LoopFrameFingerprintFactory.createObservation(before, 1, masks)
                val newPage = LoopFrameFingerprintFactory.createObservation(after, 1, masks)
                val global = globalCommonSimilarity(oldPage, newPage)
                val local = requireNotNull(SettledPageVisualPolicy.similarity(oldPage, newPage))
                val threshold = LoopFrameChangePolicy.DEFAULT_SIMILARITY_THRESHOLD
                println("SETTLED_PAGE_OWNED_BITMAP global=$global local=$local threshold=$threshold")
                assertTrue("The previous whole-page mean misses this exact owned paragraph change", global >= threshold)
                assertTrue("Supported source tiles must detect it at the unchanged default threshold", local < threshold)
                assertTrue(local < global)
                assertEquals(1f, requireNotNull(SettledPageVisualPolicy.similarity(oldPage, oldPage)), 0f)
                assertEquals(1f, requireNotNull(SettledPageVisualPolicy.similarity(newPage, newPage)), 0f)
            } finally {
                after.recycle()
            }
        } finally {
            before.recycle()
        }
    }

    private fun ownedBitmap(name: String, expectedSha: String): Bitmap {
        val assets = InstrumentationRegistry.getInstrumentation().context.assets
        val bytes = assets.open("settled-page/$name").use { it.readBytes() }
        val actualSha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") {
            (it.toInt() and 255).toString(16).padStart(2, '0')
        }
        assertEquals("Owned fixture bytes must remain exact", expectedSha, actualSha)
        return requireNotNull(BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply {
            inScaled = false
            inPreferredConfig = Bitmap.Config.ARGB_8888
        }))
    }

    private fun globalCommonSimilarity(before: SettledPageFrame, after: SettledPageFrame): Float {
        var count = 0
        var difference = 0L
        for (i in before.luminance.indices) if (before.visible[i] && after.visible[i]) {
            count++
            difference += abs((before.luminance[i].toInt() and 255) - (after.luminance[i].toInt() and 255))
        }
        assertTrue(count > 0)
        return (1.0 - difference.toDouble() / (count.toLong() * 255L)).toFloat()
    }
}
