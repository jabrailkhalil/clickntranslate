package dev.clickn.translate.ocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ArabicWordMarksTest {
    private fun reading(word: String, score: Float = .93f) = PaddleRecognitionCandidate(
        word, score, PaddleCropOrientation.ORIGINAL, ctcTokens = word.reversed().mapIndexed { i, c ->
            PaddleCtcToken(c.toString(), i, score)
        })

    @Test fun acceptsOnlyAnAdditionalVowelOnAPreviouslyUnmarkedLetter() {
        assertEquals("مَلَك", ArabicWordMarks.addition("مَلك", reading("مَلَك")))
        assertEquals("كُتِبَ", ArabicWordMarks.addition("كتِبَ", reading("كُتِبَ")))
        assertNull(ArabicWordMarks.addition("عِلم", reading("عَلَم")))
        assertNull(ArabicWordMarks.addition("مَلك", reading("مَلَك", .35f)))
        assertNull(ArabicWordMarks.addition("قلمًا", reading("قلمًَا")))
        assertNull(ArabicWordMarks.addition("مَلك", reading("مَلَكٌ")))
    }
}
