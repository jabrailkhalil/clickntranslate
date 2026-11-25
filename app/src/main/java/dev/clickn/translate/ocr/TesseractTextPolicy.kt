package dev.clickn.translate.ocr

/** Native text remains in its logical order; no visual RTL reversal or cross-paragraph joining. */
internal object TesseractTextPolicy {
    fun language(text: String): String? {
        var arabic = 0
        var latin = 0
        text.codePoints().forEach { point ->
            if (Character.isLetter(point)) when (Character.UnicodeScript.of(point)) {
                Character.UnicodeScript.ARABIC -> arabic++
                Character.UnicodeScript.LATIN -> latin++
                else -> Unit
            }
        }
        return when { arabic > 0 && arabic >= latin -> "ar"; latin > 0 -> "en"; else -> null }
    }
    fun rtl(text: String): Boolean {
        var right = 0
        var left = 0
        text.codePoints().forEach { point -> when (Character.getDirectionality(point)) {
            Character.DIRECTIONALITY_RIGHT_TO_LEFT, Character.DIRECTIONALITY_RIGHT_TO_LEFT_ARABIC -> right++
            Character.DIRECTIONALITY_LEFT_TO_RIGHT -> left++
        } }
        return right > left
    }
}
