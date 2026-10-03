// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.ColorMatrix
import android.graphics.ColorMatrixColorFilter
import android.graphics.Paint
import dev.clickn.translate.data.PreprocessOptions

/**
 * OCR 前的位图预处理：上采样 / 反色 / 二值化（Otsu）。
 *
 * 适用场景：
 * - galgame 文本框对比度低 → 二值化
 * - 暗底白字 → 反色（让识别器把白字当成黑字处理，更稳）
 * - 截屏分辨率太低 → 上采样（实测 2 倍对 ML Kit 召回率帮助明显）
 */
object BitmapPreprocessor {

    fun apply(src: Bitmap, opts: PreprocessOptions): Bitmap {
        if (!opts.anyEnabled()) return src
        var cur = src
        if (opts.upscale2x) cur = upscale(cur, 2f).also { if (it !== src) Unit }
        if (opts.invert) {
            val n = invert(cur)
            if (cur !== src) cur.recycle()
            cur = n
        }
        if (opts.binarize) {
            val n = binarizeOtsu(cur)
            if (cur !== src) cur.recycle()
            cur = n
        }
        return cur
    }

    private fun upscale(src: Bitmap, factor: Float): Bitmap {
        val w = (src.width * factor).toInt()
        val h = (src.height * factor).toInt()
        return Bitmap.createScaledBitmap(src, w, h, true)
    }

    /** 颜色反转：通道 → 255 - 通道。alpha 保留。 */
    private fun invert(src: Bitmap): Bitmap {
        val dst = Bitmap.createBitmap(src.width, src.height, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(dst)
        val matrix = ColorMatrix(floatArrayOf(
            -1f, 0f, 0f, 0f, 255f,
            0f, -1f, 0f, 0f, 255f,
            0f, 0f, -1f, 0f, 255f,
            0f, 0f, 0f, 1f, 0f
        ))
        val paint = Paint().apply { colorFilter = ColorMatrixColorFilter(matrix) }
        canvas.drawBitmap(src, 0f, 0f, paint)
        return dst
    }

    /** Otsu 自动阈值二值化。 */
    private fun binarizeOtsu(src: Bitmap): Bitmap {
        val w = src.width
        val h = src.height
        val pixels = IntArray(w * h)
        src.getPixels(pixels, 0, w, 0, 0, w, h)

        val gray = ByteArray(pixels.size)
        val hist = IntArray(256)
        for (i in pixels.indices) {
            val p = pixels[i]
            val r = (p shr 16) and 0xFF
            val g = (p shr 8) and 0xFF
            val b = p and 0xFF
            val v = (r * 299 + g * 587 + b * 114) / 1000
            gray[i] = v.toByte()
            hist[v]++
        }

        val total = pixels.size
        var sum = 0L
        for (t in 0..255) sum += t * hist[t].toLong()
        var sumB = 0L
        var wB = 0
        var maxVar = 0.0
        var threshold = 127
        for (t in 0..255) {
            wB += hist[t]
            if (wB == 0) continue
            val wF = total - wB
            if (wF == 0) break
            sumB += t * hist[t].toLong()
            val mB = sumB.toDouble() / wB
            val mF = (sum - sumB).toDouble() / wF
            val v = wB.toDouble() * wF * (mB - mF) * (mB - mF)
            if (v > maxVar) {
                maxVar = v
                threshold = t
            }
        }

        for (i in pixels.indices) {
            val v = gray[i].toInt() and 0xFF
            val nv = if (v > threshold) 0xFFFFFFFF.toInt() else 0xFF000000.toInt()
            pixels[i] = nv
        }
        val dst = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        dst.setPixels(pixels, 0, w, 0, 0, w, h)
        return dst
    }
}
