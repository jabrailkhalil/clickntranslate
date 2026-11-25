package dev.clickn.translate.capture

import android.graphics.Bitmap

/**
 * Small, immutable visual anchors for already recognized text, never screenshots. Observations
 * must be clean source frames; composited translations cannot establish the source's identity.
 */
internal class SettledTextWatch private constructor(
    val width: Int,
    val height: Int,
    val contextId: Int,
    private val samples: List<LoopRoiVisualFingerprint>,
) {
    data class Observation(val similarity: Float, val current: SettledTextWatch)

    val regionCount: Int get() = samples.size
    val regions: List<LoopTextRect> get() = samples.map { it.roi.copy() }

    fun comparable(bitmap: Bitmap, contextId: Int): Boolean =
        !bitmap.isRecycled && this.contextId == contextId && width == bitmap.width && height == bitmap.height

    /** Samples the SAME regions once, allowing the owner to replace its candidate anchor. */
    fun observe(bitmap: Bitmap, contextId: Int): Observation? {
        if (!comparable(bitmap, contextId)) return null
        val current = sample(bitmap, contextId, samples.map { it.roi }) ?: return null
        var similarity = 1f
        for (index in samples.indices) {
            similarity = minOf(similarity, LoopRoiVisualPolicy.similarity(samples[index], current.samples[index]))
        }
        return Observation(similarity, current)
    }

    fun similarity(bitmap: Bitmap, contextId: Int): Float? = observe(bitmap, contextId)?.similarity

    companion object {
        fun create(bitmap: Bitmap, contextId: Int, regions: List<LoopTextRect>): SettledTextWatch? {
            if (bitmap.isRecycled) return null
            val bounded = SettledTextWatchRegions.bound(bitmap.width, bitmap.height, regions)
            return sample(bitmap, contextId, bounded)
        }

        private fun sample(bitmap: Bitmap, contextId: Int, regions: List<LoopTextRect>): SettledTextWatch? {
            if (bitmap.isRecycled || regions.isEmpty()) return null
            val sampled = ArrayList<LoopRoiVisualFingerprint>(regions.size)
            try {
                for (region in regions) {
                    sampled += LoopRoiVisualFingerprintFactory.create(bitmap, region, contextId) ?: return null
                }
            } catch (_: IllegalArgumentException) {
                return null
            } catch (_: IllegalStateException) {
                return null
            }
            return SettledTextWatch(bitmap.width, bitmap.height, contextId, sampled)
        }
    }
}

/**
 * Keep fine anchors within one frame's crop area and reserve one union for all overflow.
 * Thus every valid source region remains covered, with at most 64 samples and twice the frame
 * area processed. The union is intentionally coarser; it does not promise character diffing.
 */
internal object SettledTextWatchRegions {
    private const val MAX_FINE_REGIONS = 63

    fun bound(width: Int, height: Int, regions: List<LoopTextRect>): List<LoopTextRect> {
        if (width <= 0 || height <= 0) return emptyList()
        val frameArea = width.toLong() * height
        val fine = ArrayList<LoopTextRect>()
        var fineArea = 0L
        var overflow: LoopTextRect? = null
        for (source in regions) {
            val region = LoopTextRect(
                source.left.coerceIn(0, width), source.top.coerceIn(0, height),
                source.right.coerceIn(0, width), source.bottom.coerceIn(0, height),
            )
            if (!region.isValid || region in fine) continue
            val area = region.width.toLong() * region.height
            if (fine.size < MAX_FINE_REGIONS && fineArea + area <= frameArea) {
                fine += region
                fineArea += area
            } else {
                overflow = overflow?.union(region) ?: region
            }
        }
        return (fine + listOfNotNull(overflow)).distinct()
    }
}
