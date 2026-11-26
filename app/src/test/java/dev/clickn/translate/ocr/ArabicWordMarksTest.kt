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

    @Test fun usesThePeakOfTheSameCollapsedVowelWithoutChangingItsAlignment() {
        val word = "مَلَك"
        val original = reading(word)
        val vowelIndex = 1 // second fatha in visual (left-to-right) order
        val uncertain = original.ctcTokens.toMutableList()
        uncertain[vowelIndex] = uncertain[vowelIndex].copy(confidence = .51f, peakConfidence = .53f)
        assertNull(ArabicWordMarks.addition("مَلك", original.copy(ctcTokens = uncertain)))
        uncertain[vowelIndex] = uncertain[vowelIndex].copy(peakConfidence = .86f)
        assertEquals(word, ArabicWordMarks.addition("مَلك", original.copy(ctcTokens = uncertain)))
        assertNull(ArabicWordMarks.addition("مَلِك", original.copy(ctcTokens = uncertain)))
    }

    @Test fun anOrphanVowelCanRegainItsLetterButCannotChangeTheRestOfTheWord() {
        assertEquals("مَلَك", ArabicWordMarks.addition("َلك", reading("مَلَك")))
        assertEquals("مَلك", ArabicWordMarks.addition("َلك", reading("مَلك")))
        assertNull(ArabicWordMarks.addition("َلك", reading("مَلَك", .73f)))
        assertNull(ArabicWordMarks.addition("لَك", reading("مَلَك")))
        assertNull(ArabicWordMarks.addition("َلق", reading("مَلَك")))
    }
}
