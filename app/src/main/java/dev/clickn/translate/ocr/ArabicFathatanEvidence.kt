package dev.clickn.translate.ocr

import android.graphics.Bitmap
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt

/** Final ـًا and ـَا can change number. Only promote a competing CTC class with two visible strokes. */
internal object ArabicFathatanEvidence {
    const val FATHA = "\u064E"
    const val FATHATAN = "\u064B"

    fun refine(crop: Bitmap, line: PaddleRecognitionCandidate, checkActive: () -> Unit): PaddleRecognitionCandidate {
        if (line.orientation != PaddleCropOrientation.ORIGINAL || line.ctcSteps <= 0 || line.targetWidth <= 0 ||
            line.widthCapped || crop.height !in 24..256 || FATHA !in line.text) return line
        val tokens = line.ctcTokens
        val stepWidth = crop.width.toDouble() * line.tensorWidth / line.targetWidth / line.ctcSteps
        var revised: MutableList<PaddleCtcToken>? = null
        var inspected = 0
        for (i in 1 until tokens.lastIndex) {
            val mark = tokens[i]
            if (mark.text != FATHA || mark.fathatanScore < maxOf(.04f, .15f * mark.confidence)) continue
            // Visual CTC runs left to right: word boundary, final alif, mark, its consonant.
            if (tokens[i - 1].text != "ا" || !isBoundary(tokens.getOrNull(i - 2)?.text)) continue
            val consonant = tokens[i + 1].text.singleOrNull() ?: continue
            if (!consonant.isLetter() || Character.UnicodeScript.of(consonant.code) != Character.UnicodeScript.ARABIC) continue
            if (++inspected > 4) break
            checkActive()
            val x = (mark.step + .5) * stepWidth
            val radius = crop.height * .32
            val left = floor(maxOf(0.0, x - radius, tokens[i - 1].step * stepWidth - .08 * crop.height)).toInt()
            val right = ceil(minOf(crop.width.toDouble(), x + radius, (tokens[i + 1].step + 1) * stepWidth + .08 * crop.height)).toInt()
            val bottom = (crop.height * .57).roundToInt()
            if (right - left < 7) continue
            val pixels = IntArray((right - left) * bottom)
            crop.getPixels(pixels, 0, right - left, left, 0, right - left, bottom)
            if (hasParallelStrokes(pixels, right - left, bottom, crop.height)) {
                val updated = revised ?: tokens.toMutableList().also { revised = it }
                updated[i] = mark.copy(text = FATHATAN)
            }
        }
        val accepted = revised ?: return line
        return line.copy(text = arabicCtcLogicalText(accepted.joinToString("") { it.text }), ctcTokens = accepted)
    }

    private fun isBoundary(text: String?): Boolean =
        text == null || text == " " || (text.length == 1 && text[0] in ".,،؛؟!?:»«()")

    private data class Stroke(val left: Int, val width: Int, val y: Double, val slope: Double)

    /** Look in source pixels before the 48px recognition resize. Touching, faint or ambiguous marks abstain. */
    fun hasParallelStrokes(pixels: IntArray, width: Int, height: Int, lineHeight: Int): Boolean {
        val histogram = IntArray(16)
        val gray = IntArray(pixels.size) { i ->
            val c = pixels[i]
            val value = ((c ushr 16 and 255) * 77 + (c ushr 8 and 255) * 150 + (c and 255) * 29) ushr 8
            histogram[value / 16]++
            value
        }
        val mode = histogram.indices.maxBy { histogram[it] }
        if (histogram[mode] < pixels.size * .50) return false
        val background = mode * 16 + 8
        val ink = BooleanArray(pixels.size) { abs(gray[it] - background) >= 84 }
        val queue = IntArray(pixels.size)
        val strokes = mutableListOf<Stroke>()
        for (start in ink.indices) {
            if (!ink[start]) continue
            ink[start] = false
            queue[0] = start
            var read = 0
            var size = 1
            var left = width
            var right = 0
            var top = height
            var bottom = 0
            var sx = 0.0
            var sy = 0.0
            var sxx = 0.0
            var sxy = 0.0
            while (read < size) {
                val at = queue[read++]
                val x = at % width
                val y = at / width
                left = minOf(left, x)
                right = maxOf(right, x)
                top = minOf(top, y)
                bottom = maxOf(bottom, y)
                sx += x
                sy += y
                sxx += x * x
                sxy += x * y
                for (ny in maxOf(0, y - 1)..minOf(height - 1, y + 1)) {
                    for (nx in maxOf(0, x - 1)..minOf(width - 1, x + 1)) {
                        val next = ny * width + nx
                        if (ink[next]) {
                            ink[next] = false
                            queue[size++] = next
                        }
                    }
                }
            }
            val w = right - left + 1
            val h = bottom - top + 1
            if (left == 0 || right == width - 1 || top == 0 || bottom == height - 1 ||
                w < maxOf(5.0, .055 * lineHeight) || w > .31 * lineHeight || w < 1.45 * h) continue
            val slope = (sxy - sx * sy / size) / (sxx - sx * sx / size)
            if (slope in -.85..-.12) strokes += Stroke(left, w, sy / size, slope)
        }
        var pairs = 0
        for ((i, a) in strokes.withIndex()) for (j in 0 until i) {
            val b = strokes[j]
            val shorter = minOf(a.width, b.width)
            val overlap = minOf(a.left + a.width, b.left + b.width) - maxOf(a.left, b.left)
            if (shorter >= .75 * maxOf(a.width, b.width) && overlap >= .78 * shorter &&
                abs(a.slope - b.slope) <= .19 && abs(a.y - b.y) in .23 * shorter.. .7 * shorter) pairs++
        }
        return pairs == 1
    }
}
