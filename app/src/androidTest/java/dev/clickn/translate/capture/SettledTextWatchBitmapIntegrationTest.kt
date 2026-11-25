package dev.clickn.translate.capture

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Typeface
import androidx.test.ext.junit.runners.AndroidJUnit4
import kotlin.math.abs
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Platform bitmap sampling of owned text; no OCR, translator, network or app-data mutations. */
@RunWith(AndroidJUnit4::class)
class SettledTextWatchBitmapIntegrationTest {
    private val textRegions = listOf(LoopTextRect(65, 805, 705, 855), LoopTextRect(65, 1005, 705, 1055))

    @Test fun aOneWordEditIsNotDilutedByTheRestOfTheWhiteScreenAndCanBecomeTheNextAnchor() {
        val before = page("valleys")
        val after = page("forests")
        try {
            val previous = requireNotNull(SettledTextWatch.create(before, 7, textRegions))
            val observation = requireNotNull(previous.observe(after, 7))
            val global = globalSimilarity(before, after)
            println("SETTLED_TEXT_WATCH_BITMAP global=$global local=${observation.similarity}")
            assertTrue("Whole-page mean can miss the word change", global >= 0.95f)
            assertTrue("Known text must detect the changed word", observation.similarity < 0.95f)
            assertEquals(1f, requireNotNull(previous.similarity(before, 7)), 0f)
            assertEquals("A stable changed page must not remain changed forever",
                1f, requireNotNull(observation.current.similarity(after, 7)), 0f)
        } finally {
            before.recycle()
            after.recycle()
        }
    }

    @Test fun pixelsOutsideCopiedTextRegionsDoNotTriggerTheTextWatch() {
        val before = page("valleys")
        val after = page("valleys")
        try {
            val suppliedRegions = textRegions.toMutableList()
            val watch = requireNotNull(SettledTextWatch.create(before, 1, suppliedRegions))
            suppliedRegions.clear()
            assertEquals(textRegions, watch.regions)
            Canvas(after).drawRect(10f, 10f, 100f, 60f, Paint().apply { color = Color.BLACK })
            assertEquals(1f, requireNotNull(watch.similarity(after, 1)), 0f)
        } finally {
            before.recycle()
            after.recycle()
        }
    }

    @Test fun fullSizeImmutableBitmapRemainsOwnedByCallerAndWatchDoesNotRetainIt() {
        val mutable = Bitmap.createBitmap(96, 48, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.WHITE) }
        val original = requireNotNull(mutable.copy(Bitmap.Config.ARGB_8888, false))
        mutable.recycle()
        val identical = requireNotNull(original.copy(Bitmap.Config.ARGB_8888, false))
        try {
            val watch = requireNotNull(SettledTextWatch.create(original, 2, listOf(LoopTextRect(0, 0, 96, 48))))
            assertFalse("Factory must not recycle its immutable full-frame input", original.isRecycled)
            assertEquals(Color.WHITE, original.getPixel(0, 0))
            original.recycle()
            assertEquals("Only byte samples remain, not the caller's bitmap",
                1f, requireNotNull(watch.similarity(identical, 2)), 0f)
        } finally {
            if (!original.isRecycled) original.recycle()
            identical.recycle()
        }
    }

    @Test fun incompatibleOrUnavailableFramesAreUnknownRatherThanChanged() {
        val before = page("valleys")
        val rotated = Bitmap.createBitmap(1600, 720, Bitmap.Config.ARGB_8888)
        val unavailable = page("valleys").apply { recycle() }
        try {
            val watch = requireNotNull(SettledTextWatch.create(before, 3, textRegions))
            assertFalse(watch.comparable(rotated, 3))
            assertNull(watch.observe(rotated, 3))
            assertNull(watch.similarity(before, 4))
            assertNull(watch.observe(unavailable, 3))
            assertNull(SettledTextWatch.create(before, 3, emptyList()))
        } finally {
            before.recycle()
            rotated.recycle()
        }
    }

    private fun page(finalWord: String): Bitmap =
        Bitmap.createBitmap(720, 1600, Bitmap.Config.ARGB_8888).apply {
            eraseColor(Color.WHITE)
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.BLACK
                textSize = 32f
                typeface = Typeface.create("sans-serif", Typeface.NORMAL)
            }
            Canvas(this).apply {
                drawText("Bright rivers run through quiet $finalWord.", 80f, 845f, paint)
                drawText("The small fox reads a useful book.", 80f, 1045f, paint)
            }
        }

    private fun globalSimilarity(a: Bitmap, b: Bitmap): Float {
        val before = LoopFrameFingerprintFactory.createObservation(a, 1, emptyList()).luminance
        val after = LoopFrameFingerprintFactory.createObservation(b, 1, emptyList()).luminance
        var difference = 0L
        for (index in before.indices) {
            difference += abs((before[index].toInt() and 255) - (after[index].toInt() and 255))
        }
        return (1.0 - difference.toDouble() / (before.size * 255L)).toFloat()
    }
}
