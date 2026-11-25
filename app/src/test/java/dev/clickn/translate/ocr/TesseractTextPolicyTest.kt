package dev.clickn.translate.ocr

import org.junit.Assert.*
import org.junit.Test

class TesseractTextPolicyTest {
    @Test fun mixedArabicEnglishKeepsLogicalTextAndUsesItsActualDominantScript() {
        val source = "هذا نص عربي مع Android يعمل على الهاتف."
        assertEquals("ar", TesseractTextPolicy.language(source))
        assertTrue(TesseractTextPolicy.rtl(source))
        assertEquals("هذا نص عربي مع Android يعمل على الهاتف.", source)
    }
    @Test fun englishParagraphsAndNumbersAreNotInventedAsArabic() {
        assertEquals("en", TesseractTextPolicy.language("Bright rivers run through quiet valleys."))
        assertFalse(TesseractTextPolicy.rtl("Bright rivers run through quiet valleys."))
        assertNull(TesseractTextPolicy.language("2026!"))
        assertFalse(TesseractTextPolicy.rtl("2026!"))
    }
}
