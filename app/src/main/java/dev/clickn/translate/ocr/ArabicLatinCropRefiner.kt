package dev.clickn.translate.ocr

import android.graphics.Bitmap
import kotlinx.coroutines.CancellationException
import timber.log.Timber

/** Same installed recognizer, bounded word crops, no extra detector/model/network request. */
internal object ArabicLatinCropRefiner {
    class Budget {
        private var count = 0
        private var pixels = 0L
        fun reserve(width: Int, height: Int): Boolean {
            val area = width.toLong() * height
            if (width <= 0 || height <= 0 || count >= 4 || area > 1_000_000L - pixels) return false
            count++; pixels += area
            return true
        }
    }

    fun refine(crop: Bitmap, original: PaddleRecognitionCandidate, budget: Budget, checkActive: () -> Unit,
        recognize: (Bitmap) -> PaddleRecognitionCandidate): PaddleRecognitionCandidate {
        if (original.orientation != PaddleCropOrientation.ORIGINAL) return original
        val plans = ArabicLatinRefinementPolicy.crops(original.ctcTokens, original.ctcSteps,
            original.tensorWidth, original.targetWidth, crop.width)
        if (plans.isEmpty()) return original
        val raw = StringBuilder(original.ctcTokens.joinToString("") { it.text })
        var changed = false
        for (plan in plans.asReversed()) {
            checkActive()
            if (!budget.reserve(plan.right - plan.left, crop.height)) continue
            var word: Bitmap? = null
            try {
                word = Bitmap.createBitmap(crop, plan.left, 0, plan.right - plan.left, crop.height)
                val candidate = recognize(word)
                checkActive()
                val replacement = candidate.text.trim()
                if (ArabicLatinRefinementPolicy.accepts(plan, replacement, candidate.ctcTokens)) {
                    raw.replace(plan.rawStart, plan.rawEnd, replacement)
                    changed = true
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                Timber.w(error, "Arabic Latin word refinement failed; keeping original recognition")
            } finally {
                word?.let { if (it !== crop && !it.isRecycled) it.recycle() }
            }
        }
        // Geometry/confidence remain those of the original line; refinement is never recursive.
        return if (changed) original.copy(text = arabicCtcLogicalText(raw.toString())) else original
    }
}
