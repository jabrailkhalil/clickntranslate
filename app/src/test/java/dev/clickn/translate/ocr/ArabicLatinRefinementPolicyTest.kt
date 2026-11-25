package dev.clickn.translate.ocr

import org.junit.Assert.*
import org.junit.Test

class ArabicLatinRefinementPolicyTest {
    private fun token(text: String, step: Int, score: Float = .9f) = PaddleCtcToken(text, step, score)
    private val actualMissingLetters = listOf(token("O", 1), token(" ", 10), token("ة", 12),
        token("م", 14), token("ل", 16), token("ك", 18))
    private val reliableWord = listOf(token("O", 1, .999f), token("C", 4, .998f), token("R", 7, .999f))

    @Test fun actualMissingLettersUseTheWordSpaceRatherThanLastRecognizedGlyph() {
        val plan = ArabicLatinRefinementPolicy.crops(actualMissingLetters, 51, 411, 411, 1018).single()
        assertEquals("O", plan.original)
        assertEquals(0, plan.left)
        assertEquals(200, plan.right)
        assertTrue(ArabicLatinRefinementPolicy.accepts(plan, "OCR", reliableWord))
    }

    @Test fun ctcCoordinatesAccountForBatchRightPadding() {
        val padded = ArabicLatinRefinementPolicy.crops(actualMissingLetters, 80, 640, 411, 1018).single()
        assertEquals(199, padded.right)
        assertTrue(padded.right < 250)
    }

    @Test fun twoIdenticalWordsKeepDistinctRawOffsetsAndSeparateSpaces() {
        val tokens = listOf(token("ة", 0), token(" ", 2), token("O", 4), token("R", 7), token(" ", 10),
            token("م", 12), token(" ", 14), token("O", 16), token(" ", 20), token("ك", 22))
        val plans = ArabicLatinRefinementPolicy.crops(tokens, 25, 200, 200, 1000)
        assertEquals(listOf(2 to 4, 7 to 8), plans.map { it.rawStart to it.rawEnd })
        val raw = StringBuilder(tokens.joinToString("") { it.text })
        plans.asReversed().forEach { raw.replace(it.rawStart, it.rawEnd, "OCR") }
        assertEquals("ة OCR م OCR ك", raw.toString())
    }

    @Test fun pureLatinPureArabicDigitsAndPunctuationEnvelopesDoNotTrigger() {
        val samples = listOf(listOf(token("O", 1), token("R", 4)), listOf(token("م", 1)),
            listOf(token("1", 1), token(" ", 3), token("م", 6)),
            listOf(token("م", 0), token(" ", 2), token("O", 4), token("/", 6), token("R", 8)))
        samples.forEach { assertTrue(ArabicLatinRefinementPolicy.crops(it, 40, 320, 320, 800).isEmpty()) }
    }

    @Test fun uncertainOrContradictingCandidatesCannotChangeTheArabicLine() {
        val plan = ArabicLatinRefinementPolicy.crops(actualMissingLetters, 51, 411, 411, 1018).single()
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan, "OCR", reliableWord.map { it.copy(confidence = .94f) }))
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan, "XYZ", reliableWord))
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan, "O", reliableWord))
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan, "OCR more", reliableWord))
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan, "Oم", reliableWord))
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan.copy(confidence = .9999f), "OCR", reliableWord))
        assertFalse(ArabicLatinRefinementPolicy.accepts(plan, "OCR", reliableWord.map { it.copy(confidence = Float.NaN) }))
    }

    @Test fun invalidCtcGeometryNeverBecomesABitmapCrop() {
        assertTrue(ArabicLatinRefinementPolicy.crops(actualMissingLetters, 0, 411, 411, 1018).isEmpty())
        assertTrue(ArabicLatinRefinementPolicy.crops(actualMissingLetters, 51, 300, 411, 1018).isEmpty())
        assertTrue(ArabicLatinRefinementPolicy.crops(actualMissingLetters.reversed(), 51, 411, 411, 1018).isEmpty())
        assertTrue(ArabicLatinRefinementPolicy.crops(actualMissingLetters, 10, 411, 411, 1018).isEmpty())
    }
}
