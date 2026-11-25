package dev.clickn.translate.ocr

/**
 * Arabic Paddle CTC predictions use the visual character order of the recognizer's training data.
 * Adapt PaddleOCR BaseRecLabelDecode.pred_reverse after CTC collapse: reverse tokens, keeping ASCII
 * letter/number/punctuation runs intact. Edge spaces are separate tokens so a visual leading Latin
 * word does not become attached to the last Arabic word. Pure Latin predictions stay unchanged.
 * This is not an RTL display transformation, nor the newer PaddleX get_display implementation.
 * https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppocr/postprocess/rec_postprocess.py
 */
internal fun arabicCtcLogicalText(prediction: String): String {
    if (prediction.codePoints().noneMatch {
            Character.isLetter(it) && Character.UnicodeScript.of(it) == Character.UnicodeScript.ARABIC
        }) return prediction
    val tokens = mutableListOf<String>()
    val latinRun = StringBuilder()
    fun flushLatin() {
        if (latinRun.isNotEmpty()) {
            val run = latinRun.toString()
            val first = run.indexOfFirst { it != ' ' }
            if (first < 0) tokens += run else {
                val last = run.indexOfLast { it != ' ' }
                if (first > 0) tokens += run.substring(0, first)
                tokens += run.substring(first, last + 1)
                if (last < run.lastIndex) tokens += run.substring(last + 1)
            }
            latinRun.setLength(0)
        }
    }
    prediction.codePoints().forEach { point ->
        if (point in 'a'.code..'z'.code || point in 'A'.code..'Z'.code ||
            point in '0'.code..'9'.code || point <= Char.MAX_VALUE.code && point.toChar() in " :*./%+-") {
            latinRun.appendCodePoint(point)
        } else {
            flushLatin()
            tokens += String(Character.toChars(point))
        }
    }
    flushLatin()
    return buildString(prediction.length) {
        for (index in tokens.lastIndex downTo 0) append(tokens[index])
    }
}
