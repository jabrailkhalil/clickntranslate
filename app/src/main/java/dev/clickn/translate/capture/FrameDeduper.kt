// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import android.graphics.Bitmap

/**
 * 帧差跳过：用 64bit dHash 比较前后帧。汉明距离 <= [threshold] 视为同一帧。
 * 这是 clicktranslate 默认 0.5s 循环 + 差分的标准做法，能挡掉绝大多数静止画面 OCR / 翻译消耗。
 */
class FrameDeduper(private val threshold: Int = 6) {

    private var lastHash: Long = 0L
    private var hasLast = false

    /** 返回是否应跳过这一帧（true = 跳过）。同时更新内部缓存。 */
    fun shouldSkip(bitmap: Bitmap): Boolean {
        val h = dHash(bitmap)
        val skip = hasLast && hammingDistance(h, lastHash) <= threshold
        lastHash = h
        hasLast = true
        return skip
    }

    fun reset() {
        hasLast = false
        lastHash = 0L
    }

    /**
     * dHash：缩小到 9x8 灰度，比较相邻像素，得到 64bit 指纹。
     */
    private fun dHash(src: Bitmap): Long {
        val scaled = Bitmap.createScaledBitmap(src, 9, 8, true)
        var hash = 0L
        for (y in 0 until 8) {
            for (x in 0 until 8) {
                val l = luminance(scaled.getPixel(x, y))
                val r = luminance(scaled.getPixel(x + 1, y))
                hash = (hash shl 1) or (if (l > r) 1L else 0L)
            }
        }
        if (scaled !== src) scaled.recycle()
        return hash
    }

    private fun luminance(argb: Int): Int {
        val r = (argb shr 16) and 0xFF
        val g = (argb shr 8) and 0xFF
        val b = argb and 0xFF
        return (r * 299 + g * 587 + b * 114) / 1000
    }

    private fun hammingDistance(a: Long, b: Long): Int = java.lang.Long.bitCount(a xor b)
}
