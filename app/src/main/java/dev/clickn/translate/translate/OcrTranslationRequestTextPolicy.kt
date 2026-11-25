package dev.clickn.translate.translate

/** Prepares one OCR block for MT; the original display text and block membership stay untouched. */
internal object OcrTranslationRequestTextPolicy {
    fun normalize(text: String): String {
        if ('\n' !in text && '\r' !in text) return text
        val lines = text.replace("\r\n", "\n").replace('\r', '\n').split('\n')
        return buildString(text.length) {
            var paragraphBoundary = false
            for (line in lines) {
                val fragment = line.trim()
                if (fragment.isEmpty()) {
                    if (isNotEmpty()) paragraphBoundary = true
                    continue
                }
                if (isNotEmpty()) {
                    when {
                        paragraphBoundary -> append("\n\n")
                        last() == '\u00ad' -> deleteCharAt(lastIndex)
                        continuesHyphenatedWord(this, fragment) -> Unit
                        needsWordSeparator(Character.codePointBefore(this, length), Character.codePointAt(fragment, 0)) -> append(' ')
                    }
                }
                append(fragment)
                paragraphBoundary = false
            }
        }
    }

    private fun needsWordSeparator(left: Int, right: Int): Boolean {
        if (isUnspacedScript(left) || isUnspacedScript(right)) return false
        return (isWordCharacter(left) || isTrailingPunctuation(left)) && isWordCharacter(right)
    }

    // Hangul is deliberately excluded: ordinary Korean words are separated by spaces.
    private fun isUnspacedScript(codePoint: Int): Boolean = when (Character.UnicodeScript.of(codePoint)) {
        Character.UnicodeScript.HAN,
        Character.UnicodeScript.HIRAGANA,
        Character.UnicodeScript.KATAKANA -> true
        else -> false
    }

    private fun continuesHyphenatedWord(before: CharSequence, after: String): Boolean =
        before.length > 1 && before.last() == '-' &&
            Character.isLetterOrDigit(Character.codePointBefore(before, before.length - 1)) &&
            Character.isLetterOrDigit(Character.codePointAt(after, 0))

    private fun isWordCharacter(codePoint: Int): Boolean = Character.isLetterOrDigit(codePoint) ||
        when (Character.getType(codePoint)) {
            Character.NON_SPACING_MARK.toInt(), Character.COMBINING_SPACING_MARK.toInt(), Character.ENCLOSING_MARK.toInt() -> true
            else -> false
        }

    private fun isTrailingPunctuation(codePoint: Int): Boolean = when (Character.getType(codePoint)) {
        Character.CONNECTOR_PUNCTUATION.toInt(),
        Character.DASH_PUNCTUATION.toInt(),
        Character.END_PUNCTUATION.toInt(),
        Character.FINAL_QUOTE_PUNCTUATION.toInt(),
        Character.OTHER_PUNCTUATION.toInt() -> true
        else -> false
    }
}
