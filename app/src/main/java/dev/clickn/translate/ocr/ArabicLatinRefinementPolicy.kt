package dev.clickn.translate.ocr

import kotlin.math.ceil
import kotlin.math.floor

/** CTC positions are in the visual, left-to-right crop, before Arabic logical reordering. */
internal data class PaddleCtcToken(val text: String, val step: Int, val confidence: Float, val fathatanScore: Float = 0f)

internal object ArabicLatinRefinementPolicy {
    data class Crop(val rawStart: Int, val rawEnd: Int, val left: Int, val right: Int,
        val original: String, val confidence: Float)

    /** Space emissions bound a word even when its CTC prediction has dropped interior letters. */
    fun crops(tokens: List<PaddleCtcToken>, steps: Int, tensorWidth: Int,
        contentWidth: Int, cropWidth: Int): List<Crop> {
        if (steps <= 0 || contentWidth <= 0 || tensorWidth < contentWidth || cropWidth <= 0 ||
            tokens.any { it.step !in 0 until steps } ||
            tokens.zipWithNext().any { (a, b) -> a.step >= b.step } ||
            tokens.none { token -> token.text.any { Character.UnicodeScript.of(it.code) == Character.UnicodeScript.ARABIC } }) return emptyList()
        val scale = cropWidth.toDouble() * tensorWidth / contentWidth / steps
        val offsets = IntArray(tokens.size + 1)
        tokens.indices.forEach { offsets[it + 1] = offsets[it] + tokens[it].text.length }
        val result = mutableListOf<Crop>()
        var i = 0
        while (i < tokens.size) {
            if (!isWord(tokens[i].text)) { i++; continue }
            val start = i
            while (i < tokens.size && isWord(tokens[i].text)) i++
            val before = tokens.getOrNull(start - 1)
            val after = tokens.getOrNull(i)
            // Punctuation/URLs and missing separators have ambiguous word geometry.
            if (before != null && before.text != " " || after != null && after.text != " ") continue
            val word = tokens.subList(start, i).joinToString("") { it.text }
            if (word.length !in 1..62 || word.none { it in 'a'..'z' || it in 'A'..'Z' }) continue
            val left = before?.let { floor(it.step * scale).toInt() } ?: 0
            val right = after?.let { ceil(it.step * scale).toInt() } ?: cropWidth
            if (left < 0 || right > cropWidth || right <= left) continue
            result += Crop(offsets[start], offsets[i], left, right, word,
                tokens.subList(start, i).map { it.confidence }.average().toFloat())
        }
        return result
    }

    /** Only recover missing letters; unrelated, weaker, shortened or mixed-script words stay put. */
    fun accepts(crop: Crop, replacement: String, tokens: List<PaddleCtcToken>): Boolean {
        if (!isWord(replacement) || replacement.length - crop.original.length !in 1..2 || tokens.isEmpty() ||
            tokens.any { !it.confidence.isFinite() || it.confidence < .95f } ||
            !crop.confidence.isFinite()) return false
        val score = tokens.map { it.confidence }.average()
        if (score < .98 || score <= crop.confidence) return false
        var matched = 0
        replacement.forEach { if (matched < crop.original.length && it == crop.original[matched]) matched++ }
        return matched == crop.original.length
    }

    private fun isWord(text: String) = text.isNotEmpty() &&
        text.all { it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' }
}
