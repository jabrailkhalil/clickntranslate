package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.Rect
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt
import kotlinx.coroutines.CancellationException
import timber.log.Timber

/** Read a partly vocalised word at two scales. Preserve every base letter and every existing mark. */
internal object ArabicWordMarks {
    private const val SHORT_VOWELS = "َُِ"
    private const val MARKS = "ًٌٍَُِّْ"

    private fun arabicLetter(c: Char) = c.isLetter() && Character.UnicodeScript.of(c.code) == Character.UnicodeScript.ARABIC
    private fun wordToken(t: PaddleCtcToken) = t.text.singleOrNull()?.let { it in MARKS || arabicLetter(it) } == true

    /** A result is eligible only when removing one short vowel recovers the original word verbatim. */
    fun addition(original: String, reading: PaddleRecognitionCandidate): String? {
        val chars = reading.ctcTokens.asReversed()
        val word = reading.text
        if (word.length != original.length + 1 || chars.size != word.length ||
            chars.indices.any { chars[it].text.singleOrNull() != word[it] }) return null
        for (i in 1 until word.lastIndex) {
            if (word[i] !in SHORT_VOWELS || !arabicLetter(word[i - 1]) || !arabicLetter(word[i + 1]) ||
                chars[i].confidence !in .6f..1f || word.removeRange(i, i + 1) != original) continue
            return word
        }
        return null
    }

    class Budget {
        private var remaining = 2
        fun reserve(): Boolean {
            if (remaining == 0) return false
            remaining--
            return true
        }
        val exhausted get() = remaining == 0
    }

    fun refine(source: Bitmap, quad: DBPostprocessor.Quad, line: PaddleRecognitionCandidate,
        budget: Budget, checkActive: () -> Unit, read: (Bitmap) -> PaddleRecognitionCandidate): PaddleRecognitionCandidate {
        if (budget.exhausted || line.orientation != PaddleCropOrientation.ORIGINAL || line.widthCapped ||
            line.ctcSteps <= 0 || line.targetWidth <= 0 || line.text.none { it in SHORT_VOWELS } ||
            quad.height !in 22f..240f || abs(quad.p0.y - quad.p1.y) > quad.height * .16f ||
            abs(quad.p3.y - quad.p2.y) > quad.height * .16f) return line
        val tokens = line.ctcTokens
        val raw = StringBuilder(tokens.joinToString("") { it.text })
        if (arabicCtcLogicalText(raw.toString()) != line.text) return line
        val left = (quad.p0.x + quad.p3.x) * .5f
        val right = (quad.p1.x + quad.p2.x) * .5f
        val stepWidth = (right - left) * line.tensorWidth / line.targetWidth / line.ctcSteps
        val extra = quad.height * .24f
        val y0 = floor(minOf(quad.p0.y, quad.p1.y) - extra).toInt().coerceAtLeast(0)
        val y1 = ceil(maxOf(quad.p2.y, quad.p3.y) + extra).toInt().coerceAtMost(source.height)
        if (stepWidth <= 0f || y1 <= y0) return line
        var i = tokens.size
        var changed = false
        // Work backwards so replacements never move the offsets of the next word.
        while (i > 0 && !budget.exhausted) {
            if (!wordToken(tokens[i - 1])) {
                i--
                continue
            }
            val end = i
            while (i > 0 && wordToken(tokens[i - 1])) i--
            val before = tokens.getOrNull(i - 1)
            val after = tokens.getOrNull(end)
            if (before != null && before.text != " " || after != null && after.text != " ") continue
            val word = tokens.subList(i, end).asReversed().joinToString("") { it.text }
            if (word.length !in 3..18 || word.none { it in SHORT_VOWELS } ||
                (0 until word.lastIndex).none { arabicLetter(word[it]) && arabicLetter(word[it + 1]) }) continue
            val x0 = floor(before?.let { left + (it.step + .5f) * stepWidth } ?: left).toInt().coerceAtLeast(0)
            val x1 = ceil(after?.let { left + (it.step + .5f) * stepWidth } ?: right).toInt().coerceAtMost(source.width)
            val width = x1 - x0
            val height = y1 - y0
            if (width < 8 || width.toLong() * height > 130_000L || !budget.reserve()) continue
            try {
                val corrected = reread(source, Rect(x0, y0, x1, y1), quad, word, checkActive, read) ?: continue
                val offset = tokens.subList(0, i).sumOf { it.text.length }
                raw.replace(offset, offset + word.length, corrected.reversed())
                changed = true
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Timber.w(e, "Arabic vowel check skipped")
            }
        }
        return if (changed) line.copy(text = arabicCtcLogicalText(raw.toString())) else line
    }

    private fun reread(source: Bitmap, region: Rect, quad: DBPostprocessor.Quad, word: String,
        checkActive: () -> Unit, read: (Bitmap) -> PaddleRecognitionCandidate): String? {
        checkActive()
        val width = region.width()
        val height = region.height()
        val pixels = IntArray(width * height)
        source.getPixels(pixels, 0, width, region.left, region.top, width, height)
        val bounds = inkBounds(pixels, width, height) ?: return null
        // A second view can recover a detached mark when the detector grazes the ink.
        val edge = maxOf(1f, quad.height * .035f)
        if (region.top + bounds.top > minOf(quad.p0.y, quad.p1.y) + edge &&
            region.top + bounds.bottom < maxOf(quad.p2.y, quad.p3.y) - edge) return null
        val tight = maxOf(2, (bounds.height() * .04f).roundToInt())
        val loose = maxOf(tight + 2, (bounds.height() * .12f).roundToInt())
        fun cropBounds(pad: Int) = Rect(maxOf(0, bounds.left - tight), maxOf(0, bounds.top - pad),
            minOf(width, bounds.right + tight), minOf(height, bounds.bottom + pad))
        val first = cropBounds(tight)
        val second = cropBounds(loose)
        if (first == second) return null
        fun observe(box: Rect): String? {
            checkActive()
            val image = Bitmap.createBitmap(pixels, box.top * width + box.left, width, box.width(), box.height(),
                Bitmap.Config.ARGB_8888)
            return try {
                val prediction = read(image)
                checkActive()
                addition(word, prediction)
            } finally {
                image.recycle()
            }
        }
        val proposal = observe(first) ?: return null
        return proposal.takeIf { observe(second) == it }
    }

    /** Uniform screenshot backgrounds only. Keep the complete ink bounds, including detached marks. */
    private fun inkBounds(pixels: IntArray, width: Int, height: Int): Rect? {
        fun luma(c: Int) = ((c ushr 16 and 255) * 77 + (c ushr 8 and 255) * 150 + (c and 255) * 29) ushr 8
        val bands = IntArray(16)
        for (x in 0 until width) {
            bands[luma(pixels[x]) / 16]++
            bands[luma(pixels[(height - 1) * width + x]) / 16]++
        }
        val band = bands.indices.maxBy { bands[it] }
        if (bands[band] < 1.6 * width || band !in 0..4 && band !in 11..15) return null
        val bg = band * 16 + 8
        var l = width
        var t = height
        var r = -1
        var b = -1
        var backgroundCount = 0
        for (i in pixels.indices) {
            val c = luma(pixels[i])
            if (abs(c - bg) < 32) backgroundCount++
            if (abs(c - bg) >= 52) {
                l = minOf(l, i % width)
                r = maxOf(r, i % width)
                t = minOf(t, i / width)
                b = maxOf(b, i / width)
            }
            if (band < 8) pixels[i] = pixels[i] xor 0x00ffffff
        }
        if (backgroundCount < .58 * pixels.size || r - l < 5 || b - t < 8 || t == 0 || b == height - 1) return null
        return Rect(l, t, r + 1, b + 1)
    }
}
