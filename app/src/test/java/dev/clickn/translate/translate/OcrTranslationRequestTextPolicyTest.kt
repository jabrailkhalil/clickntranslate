package dev.clickn.translate.translate

import org.junit.Assert.assertEquals
import org.junit.Test

class OcrTranslationRequestTextPolicyTest {
    @Test fun knownFixtureWrapsBecomeTwoSeparateCoherentRequestTexts() {
        val blocks = listOf("Bright rivers run through quiet\nvalleys.", "The small orange fox reads a\r\nuseful book.")
        assertEquals(listOf("Bright rivers run through quiet valleys.", "The small orange fox reads a useful book."),
            blocks.map(OcrTranslationRequestTextPolicy::normalize))
        assertEquals("Bright rivers run through quiet\nvalleys.", blocks.first())
    }

    @Test fun wordScriptsKeepTheirWordBoundaryIncludingArabicMarksAndHangul() {
        val cases = listOf(
            "Bright rivers run through quiet\nvalleys." to "Bright rivers run through quiet valleys.",
            "Яркие реки бегут\rпо тихим долинам." to "Яркие реки бегут по тихим долинам.",
            "هذا نصٌّ عربيٌّ\nمتصل في فقرة واحدة." to "هذا نصٌّ عربيٌّ متصل في فقرة واحدة.",
            "밝은 강물이 조용한\n계곡을 흐릅니다." to "밝은 강물이 조용한 계곡을 흐릅니다.",
            "Hello,\nworld!" to "Hello, world!",
            "Level 1\n2026" to "Level 1 2026",
        )
        cases.forEach { (source, expected) -> assertEquals(source, expected, OcrTranslationRequestTextPolicy.normalize(source)) }
    }

    @Test fun hanAndKanaSoftWrapsDoNotIntroduceWordSpacesOrSplitSupplementaryCharacters() {
        val cases = listOf(
            "明亮的河流穿过\n安静的山谷。" to "明亮的河流穿过安静的山谷。",
            "明るい川は静かな\n谷を流れる。" to "明るい川は静かな谷を流れる。",
            "第一句。\n第二句。" to "第一句。第二句。",
            "\uD840\uDC00\n\uD840\uDC01" to "\uD840\uDC00\uD840\uDC01",
        )
        cases.forEach { (source, expected) -> assertEquals(source, expected, OcrTranslationRequestTextPolicy.normalize(source)) }
    }

    @Test fun blankLinesRemainParagraphBoundariesInsteadOfJoiningIndependentParagraphs() {
        val source = "Bright rivers run through quiet\nvalleys.\r\n \t\r\nThe small orange fox reads a\nuseful book."
        assertEquals("Bright rivers run through quiet valleys.\n\nThe small orange fox reads a useful book.",
            OcrTranslationRequestTextPolicy.normalize(source))
        assertEquals("第一句\n\n第二句", OcrTranslationRequestTextPolicy.normalize("第一句\n\n第二句"))
        assertEquals("first\n\nsecond", OcrTranslationRequestTextPolicy.normalize("\nfirst\n\n\nsecond\n"))
    }

    @Test fun onlyExplicitSoftHyphenAtASoftWrapIsRemovedWithoutGuessingHardHyphenMeaning() {
        val cases = listOf(
            "inter\u00ad\nnational" to "international",
            "co\u00ad  \r\n  operate" to "cooperate",
            "well-\nknown" to "well-known",
            "state-of-\nthe-art" to "state-of-the-art",
            "2026-\n2027" to "2026-2027",
            "-\nItem" to "- Item",
            "words -\nItem" to "words - Item",
            "well-known" to "well-known",
            "inter\u00ad\n\nnational" to "inter\u00ad\n\nnational",
            "pro\u00adgram" to "pro\u00adgram",
        )
        cases.forEach { (source, expected) -> assertEquals(source, expected, OcrTranslationRequestTextPolicy.normalize(source)) }
    }

    @Test fun preparationNeverConcatenatesIndependentOcrBlocks() {
        assertEquals(listOf("Bright rivers run through quiet", "valleys."),
            listOf("Bright rivers run through quiet", "valleys.").map(OcrTranslationRequestTextPolicy::normalize))
    }

    @Test fun untouchedSingleLinesAndEmptyInputsKeepTheirExistingContract() {
        assertEquals("  keep  spacing  ", OcrTranslationRequestTextPolicy.normalize("  keep  spacing  "))
        assertEquals("", OcrTranslationRequestTextPolicy.normalize(""))
        assertEquals("", OcrTranslationRequestTextPolicy.normalize("\r\n \t\n"))
    }
}
