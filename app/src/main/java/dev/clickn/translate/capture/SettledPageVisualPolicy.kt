// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.sqrt

/** Samples retain their visibility separately; an obscured pixel is not a black source pixel. */
internal data class SettledPageFrame(
    val width: Int,
    val height: Int,
    val contextId: Int,
    val luminance: ByteArray,
    val visible: BooleanArray,
)

internal object SettledPageVisualPolicy {
    // A tiny exposed sliver cannot establish page identity or stability.
    private const val MIN_VISIBLE_FRACTION = 0.10f
    private const val TILE_SIZE = 8

    fun visibility(
        width: Int,
        height: Int,
        sampleSize: Int,
        exclusions: List<OverlayCaptureRect>,
    ): BooleanArray {
        require(width > 0 && height > 0 && sampleSize > 0)
        val visible = BooleanArray(sampleSize * sampleSize) { true }
        exclusions.forEach { rect ->
            if (rect.isEmpty || rect.right <= 0 || rect.bottom <= 0 || rect.left >= width || rect.top >= height) {
                return@forEach
            }
            // Guard one sample cell for filtering and rounded/shadowed window edges.
            val left = (floor(rect.left.coerceAtLeast(0) * sampleSize.toDouble() / width).toInt() - 1).coerceAtLeast(0)
            val top = (floor(rect.top.coerceAtLeast(0) * sampleSize.toDouble() / height).toInt() - 1).coerceAtLeast(0)
            val right = (ceil(rect.right.coerceAtMost(width) * sampleSize.toDouble() / width).toInt() + 1).coerceAtMost(sampleSize)
            val bottom = (ceil(rect.bottom.coerceAtMost(height) * sampleSize.toDouble() / height).toInt() + 1).coerceAtMost(sampleSize)
            for (y in top until bottom) for (x in left until right) visible[y * sampleSize + x] = false
        }
        return visible
    }

    fun comparable(a: SettledPageFrame, b: SettledPageFrame): Boolean =
        a.width == b.width && a.height == b.height && a.contextId == b.contextId &&
            a.luminance.size == b.luminance.size

    /**
     * Compare both the whole source and supported local changes on the existing small sample.
     * A local signal needs three edge-connected tiles with at least 75% common visible samples
     * each, so a single blink or a small clock does not outweigh an otherwise stable page.
     * The score remains normalized luminance similarity: higher thresholds are more sensitive.
     * Tiny changes confined to one/two tiles may still be ignored; this is not character diffing.
     * Null means insufficient common source content; do not clear or resubmit a page.
     */
    fun similarity(a: SettledPageFrame, b: SettledPageFrame): Float? {
        if (!comparable(a, b) || a.luminance.isEmpty() ||
            a.visible.size != a.luminance.size || b.visible.size != b.luminance.size
        ) return null
        val sampleSide = sqrt(a.luminance.size.toDouble()).toInt()
        // Production observations are 96x96. Keep the previous global comparison for any
        // non-square input instead of guessing a row layout for its sample bytes.
        val tileColumns = if (sampleSide * sampleSide == a.luminance.size) {
            (sampleSide + TILE_SIZE - 1) / TILE_SIZE
        } else 0
        val tileCounts = IntArray(tileColumns * tileColumns)
        val tileDifferences = LongArray(tileCounts.size)
        var count = 0
        var difference = 0L
        for (i in a.luminance.indices) {
            if (!a.visible[i] || !b.visible[i]) continue
            val delta = abs((a.luminance[i].toInt() and 255) - (b.luminance[i].toInt() and 255))
            count++
            difference += delta
            if (tileColumns > 0) {
                val tile = (i / sampleSide / TILE_SIZE) * tileColumns + (i % sampleSide / TILE_SIZE)
                tileCounts[tile]++
                tileDifferences[tile] += delta
            }
        }
        if (count == 0 || count.toFloat() / a.luminance.size < MIN_VISIBLE_FRACTION) return null
        val globalDifference = difference.toDouble() / (count.toLong() * 255L)
        if (tileColumns == 0) return (1.0 - globalDifference).toFloat().coerceIn(0f, 1f)
        val localDifferences = DoubleArray(tileCounts.size) { -1.0 }
        for (tile in localDifferences.indices) {
            val x = (tile % tileColumns) * TILE_SIZE
            val y = (tile / tileColumns) * TILE_SIZE
            val area = minOf(TILE_SIZE, sampleSide - x) * minOf(TILE_SIZE, sampleSide - y)
            if (tileCounts[tile] * 4 >= area * 3) {
                localDifferences[tile] = tileDifferences[tile].toDouble() / (tileCounts[tile].toLong() * 255L)
            }
        }
        var supportedDifference = 0.0
        for (tile in localDifferences.indices) {
            val own = localDifferences[tile]
            if (own < 0.0) continue
            val x = tile % tileColumns
            val y = tile / tileColumns
            var strongestNeighbour = -1.0
            var secondNeighbour = -1.0
            for (direction in 0..3) {
                val neighbour = when (direction) {
                    0 -> if (x > 0) tile - 1 else -1
                    1 -> if (x + 1 < tileColumns) tile + 1 else -1
                    2 -> if (y > 0) tile - tileColumns else -1
                    else -> if (y + 1 < tileColumns) tile + tileColumns else -1
                }
                if (neighbour < 0) continue
                val value = localDifferences[neighbour]
                if (value > strongestNeighbour) {
                    secondNeighbour = strongestNeighbour
                    strongestNeighbour = value
                } else if (value > secondNeighbour) {
                    secondNeighbour = value
                }
            }
            // Every connected three-tile group has a centre with two edge neighbours.
            // Its weakest difference is the threshold-independent support strength.
            if (secondNeighbour >= 0.0) {
                supportedDifference = maxOf(supportedDifference, minOf(own, secondNeighbour))
            }
        }
        return (1.0 - maxOf(globalDifference, supportedDifference)).toFloat().coerceIn(0f, 1f)
    }
}
