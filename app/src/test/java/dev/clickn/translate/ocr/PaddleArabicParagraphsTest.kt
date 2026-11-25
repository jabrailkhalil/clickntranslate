package dev.clickn.translate.ocr

import org.junit.Assert.assertEquals
import org.junit.Test

class PaddleArabicParagraphsTest {
    @Test fun ownedPageGeometryKeepsEachThreeLineParagraphAndTheEnglishButtonSeparate() {
        val rows = listOf(
            line("تجري الأنهار الهادئة بين الجبال", 203, 746, 1187, 856),
            line("وتصل إلى قرية صغيرة يسكنها", 229, 909, 1183, 994),
            line("أناس طيبون", 775, 1044, 1182, 1149),
            line("يقرأ الثعلب الصغير كتابا عن السفر", 110, 1440, 1186, 1535),
            line("كل مساء ويستخدم كلمة OCR", 186, 1593, 1186, 1686),
            line("لوصف التعرف على النص", 400, 1750, 1186, 1845),
            line("Share owned photo to Clickn QA", 282, 2580, 992, 2626),
        )
        assertEquals(listOf(listOf(0, 1, 2), listOf(3, 4, 5), listOf(6)), groupPaddleArabicParagraphRows(rows))
    }

    @Test fun twoArabicColumnsDoNotBecomeOneParagraph() {
        val rows = listOf(line("عمود أول", 40, 10, 340, 60), line("عمود ثان", 540, 10, 840, 60),
            line("تكملة أولى", 40, 85, 340, 135), line("تكملة ثانية", 540, 85, 840, 135))
        assertEquals(listOf(listOf(0, 2), listOf(1, 3)), groupPaddleArabicParagraphRows(rows))
    }

    @Test fun aLatinFragmentInTheSameRtlRowStaysInLogicalReadingOrder() {
        val rows = listOf(line("كل مساء ويستخدم كلمة", 400, 100, 1180, 180), line("OCR", 180, 100, 380, 180))
        assertEquals(listOf(listOf(0, 1)), groupPaddleArabicTextRows(rows))
    }

    @Test fun separateArabicWordsOnASingleBaselineReachTheTranslatorInReadingOrder() {
        val words = listOf(line("قلمًا", 185, 53, 259, 93), line("اشترى", 410, 54, 525, 104),
            line("جديدًا", 45, 55, 168, 102), line("الطالب", 271, 55, 393, 95))
        assertEquals(listOf(listOf(1, 3, 0, 2)), groupPaddleArabicTextRows(words))
    }

    @Test fun tightlySpacedArabicColumnsKeepTheirRecurringGutter() {
        val rows = listOf(line("يمين", 220, 10, 390, 54), line("يسار", 40, 10, 204, 54),
            line("متابعة", 220, 76, 390, 120), line("أخرى", 43, 76, 203, 120))
        assertEquals(listOf(listOf(0), listOf(1), listOf(2), listOf(3)), groupPaddleArabicTextRows(rows))
    }

    @Test fun separateLatinWordsInArabicAreReadLeftToRightWithinTheirRun() {
        // Visual order, left to right: اليوم | Android | Studio | نستخدم
        val fragments = listOf(
            line("Studio", 320, 100, 425, 170), line("اليوم", 10, 100, 110, 170),
            line("نستخدم", 435, 100, 580, 170), line("Android", 120, 100, 310, 170),
        )
        val logical = groupPaddleArabicTextRows(fragments).single().map { fragments[it].text }
        assertEquals(listOf("نستخدم", "Android", "Studio", "اليوم"), logical)
    }

    @Test fun aVersionNumberInAnEnglishNameStaysWithTheName() {
        val fragments = listOf(
            line("اليوم", 10, 100, 110, 170), line("Android", 120, 100, 260, 170),
            line("Studio", 270, 100, 375, 170), line("2026", 385, 100, 465, 170),
            line("نستخدم", 475, 100, 620, 170),
        )
        val logical = groupPaddleArabicTextRows(fragments).single().map { fragments[it].text }
        assertEquals(listOf("نستخدم", "Android", "Studio", "2026", "اليوم"), logical)
    }

    @Test fun aLargeHeadingCannotAbsorbSmallerBodyText() {
        val rows = listOf(line("عنوان", 450, 10, 900, 110), line("هذه بداية الفقرة", 100, 135, 900, 175))
        assertEquals(listOf(listOf(0), listOf(1)), groupPaddleArabicParagraphRows(rows))
    }

    private fun line(text: String, left: Int, top: Int, right: Int, bottom: Int) =
        PaddleArabicTextLine(text, MergeDebugRect(left, top, right, bottom))
}
