package dev.clickn.translate.overlay

import java.text.Bidi
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HorizontalRtlTextTest {
    @Test fun russianTranslationOfAnRtlSourceRetainsLeftToRightLetterRuns() {
        val text = horizontalRtlDisplayText("Спокойные реки текут между горами, они несут прохладу.")
        val layout = Bidi(text, Bidi.DIRECTION_DEFAULT_RIGHT_TO_LEFT)

        assertTrue("The target paragraph is Russian, despite the RTL source", layout.baseIsLeftToRight())
        assertRunDirection(text, layout, "Спокойные реки текут между горами", rightToLeft = false)
    }

    @Test fun arabicTargetRetainsArabicAndEmbeddedLatinRunDirections() {
        val text = horizontalRtlDisplayText("نهر هادئ بين الجبال (ClicknTranslate 2026).")
        val layout = Bidi(text, Bidi.DIRECTION_DEFAULT_LEFT_TO_RIGHT)

        assertFalse("Arabic target must not inherit the source's LTR direction", layout.baseIsLeftToRight())
        assertRunDirection(text, layout, "نهر هادئ بين الجبال", rightToLeft = true)
        assertRunDirection(text, layout, "ClicknTranslate 2026", rightToLeft = false)
    }

    @Test fun mixedRussianTargetKeepsEachScriptAndNumericRunReadable() {
        val text = horizontalRtlDisplayText("Перевод: العربية (QA 2026), готов.")
        val layout = Bidi(text, Bidi.DIRECTION_DEFAULT_RIGHT_TO_LEFT)

        assertRunDirection(text, layout, "Перевод", rightToLeft = false)
        assertRunDirection(text, layout, "العربية", rightToLeft = true)
        assertRunDirection(text, layout, "QA 2026", rightToLeft = false)
        assertRunDirection(text, layout, "готов", rightToLeft = false)
    }

    @Test fun paragraphsAndGraphemesStayInTheOriginalLogicalText() {
        val original = "Первый абзац 😀e\u0301\r\n\r\nنهر هادئ\nПоследний абзац."
        assertEquals(original, horizontalRtlDisplayText(original))
        assertEquals("", horizontalRtlDisplayText(""))
    }

    private fun assertRunDirection(text: String, layout: Bidi, run: String, rightToLeft: Boolean) {
        val start = text.indexOf(run)
        assertTrue("Missing test run: $run", start >= 0)
        run.indices.filter { run[it].isLetterOrDigit() }.forEach { index ->
            assertEquals(
                "Wrong visual run direction for '${run[index]}' in '$run'",
                if (rightToLeft) 1 else 0,
                layout.getLevelAt(start + index) and 1,
            )
        }
    }
}
