package dev.clickn.translate.overlay

import android.text.Layout
import android.util.TypedValue
import android.view.View
import android.view.ViewGroup
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Real framework TextView shaping and wrapped-line positions; no capture, models or network. */
@RunWith(AndroidJUnit4::class)
class HorizontalTranslationBidiIntegrationTest {
    @Test fun sourceDirectionCannotReverseTranslatedRunsDuringInitialOrStreamingLayout() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.runOnMainSync {
            val view = StyledTranslationTextView(instrumentation.targetContext).apply {
                layoutParams = ViewGroup.LayoutParams(400, ViewGroup.LayoutParams.WRAP_CONTENT)
                setTextSize(TypedValue.COMPLEX_UNIT_PX, 32f)
                setSingleLine(false)
                horizontalRightToLeft = true
            }
            // The same update entry point is used both on creation and for later translated chunks.
            layout(view, "Спокойные реки")
            assertTargetRun(view, "Спокойные", rightToLeft = false)

            val russian = "Спокойные реки текут между горами, они несут прохладу.\n" +
                "Лёгкий ветер несёт осенние листья."
            layout(view, russian)
            assertEquals(russian, view.text.toString())
            assertTrue("The regression must exercise wrapped target lines", view.layout.lineCount > 2)
            assertTargetRun(view, "Спокойные", rightToLeft = false)
            assertTargetRun(view, "Лёгкий", rightToLeft = false)

            // Arabic targets of an LTR source still shape RTL, while an embedded Latin word reads LTR.
            view.horizontalRightToLeft = false
            layout(view, "نهر هادئ بين الجبال (ClicknTranslate 2026).")
            assertEquals(Layout.DIR_RIGHT_TO_LEFT, view.layout.getParagraphDirection(0))
            assertTargetRun(view, "نهر", rightToLeft = true)
            assertTargetRun(view, "ClicknTranslate", rightToLeft = false)
        }
    }

    private fun layout(view: StyledTranslationTextView, text: String) {
        view.setTranslationText(text)
        view.measure(
            View.MeasureSpec.makeMeasureSpec(400, View.MeasureSpec.EXACTLY),
            View.MeasureSpec.makeMeasureSpec(2000, View.MeasureSpec.AT_MOST),
        )
        view.layout(0, 0, view.measuredWidth, view.measuredHeight)
    }

    private fun assertTargetRun(view: StyledTranslationTextView, run: String, rightToLeft: Boolean) {
        val start = view.text.indexOf(run)
        assertTrue("Missing test run: $run", start >= 0)
        val layout = view.layout
        // Interior caret positions avoid the two valid caret affinities at a bidi run boundary.
        val first = start + 1
        val second = start + 2
        assertEquals("The sampled letters must share a line", layout.getLineForOffset(first), layout.getLineForOffset(second))
        val firstX = layout.getPrimaryHorizontal(first)
        val secondX = layout.getPrimaryHorizontal(second)
        assertTrue(
            "Wrong glyph order for '$run': x($first)=$firstX, x($second)=$secondX",
            if (rightToLeft) secondX < firstX else secondX > firstX,
        )
    }
}
