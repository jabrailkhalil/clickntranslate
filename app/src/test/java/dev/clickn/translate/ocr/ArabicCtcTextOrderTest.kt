package dev.clickn.translate.ocr

import org.junit.Assert.assertEquals
import org.junit.Test

class ArabicCtcTextOrderTest {
    @Test fun visualArabicPredictionBecomesLogicalWords() {
        assertEquals("مرحبا العالم", arabicCtcLogicalText("ملاعلا ابحرم"))
    }

    @Test fun mixedArabicKeepsTheEmbeddedLatinWordReadable() {
        assertEquals("يستخدم كلمة OCR للتعرف على النص.",
            arabicCtcLogicalText(".صنلا ىلع فرعتلل OCR ةملك مدختسي"))
    }

    @Test fun officialAsciiNumbersAndPunctuationRunIsNeverReversed() {
        assertEquals("مرحبا 12.5%+3/4:* OCR عالم",
            arabicCtcLogicalText("ملاع 12.5%+3/4:* OCR ابحرم"))
        assertEquals("Share owned photo to Clickn QA", arabicCtcLogicalText("Share owned photo to Clickn QA"))
        assertEquals("Click'n'Translate (QA 2026)!", arabicCtcLogicalText("Click'n'Translate (QA 2026)!"))
    }

    @Test fun actualLeadingLatinPredictionKeepsItsWordBoundaryAfterArabicReordering() {
        assertEquals("كل مساء، ويستخدم كلمة OR", arabicCtcLogicalText("OR ةملك مدختسيو ،ءاسم لك"))
        assertEquals("OCR كلمة", arabicCtcLogicalText("ةملك OCR"))
    }

    @Test fun emptyAndSupplementaryCodepointsRemainValidText() {
        assertEquals("", arabicCtcLogicalText(""))
        assertEquals("مرحبا 😀 عالم", arabicCtcLogicalText("ملاع 😀 ابحرم"))
    }
}
