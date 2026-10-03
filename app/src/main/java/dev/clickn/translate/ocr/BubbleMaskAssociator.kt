// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import dev.clickn.translate.ocr.BubbleClusterer.IntRect
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/**
 * Associates OCR groups with model speech-bubble instances without changing production rendering.
 *
 * A match must be supported by both geometry and actual mask pixels. This prevents a large model
 * box from claiming nearby sound effects or narration that merely happen to overlap its bounds.
 * Multiple OCR groups may intentionally map to the same model bubble so a future stage can merge
 * detector-split text that belongs to one speech bubble.
 */
internal object BubbleMaskAssociator {

    data class OcrGroup(
        val contentBounds: IntRect,
        val memberBounds: List<IntRect>,
    )

    enum class Reason {
        MATCHED_CENTER_AND_COVERAGE,
        MATCHED_COVERAGE,
        UNMATCHED_NO_MODEL_BUBBLE,
        UNMATCHED_LOW_COVERAGE,
        UNMATCHED_AMBIGUOUS,
    }

    data class Association(
        val ocrGroupIndex: Int,
        val modelBubbleIndex: Int?,
        val reason: Reason,
        val score: Float,
        val memberMaskCoverage: Float,
        val contentBoxCoverage: Float,
        val centerInsideMask: Boolean,
    ) {
        val matched: Boolean
            get() = modelBubbleIndex != null
    }

    private data class Candidate(
        val modelBubbleIndex: Int,
        val score: Float,
        val memberMaskCoverage: Float,
        val contentBoxCoverage: Float,
        val centerInsideMask: Boolean,
        val acceptedReason: Reason?,
    )

    fun associate(
        width: Int,
        height: Int,
        modelBubbles: List<BubbleSegmentationPostprocessor.Detection>,
        instanceMasks: List<BubbleSegmentationPostprocessor.InstanceMask>,
        ocrGroups: List<OcrGroup>,
    ): List<Association> {
        require(width > 0 && height > 0)
        require(instanceMasks.size == modelBubbles.size)
        return ocrGroups.mapIndexed { groupIndex, group ->
            associateOne(
                groupIndex = groupIndex,
                group = group,
                width = width,
                height = height,
                modelBubbles = modelBubbles,
                instanceMasks = instanceMasks,
            )
        }
    }

    private fun associateOne(
        groupIndex: Int,
        group: OcrGroup,
        width: Int,
        height: Int,
        modelBubbles: List<BubbleSegmentationPostprocessor.Detection>,
        instanceMasks: List<BubbleSegmentationPostprocessor.InstanceMask>,
    ): Association {
        val content = clamp(group.contentBounds, width, height)
        val memberBounds = group.memberBounds
            .ifEmpty { listOf(content) }
            .map { clamp(it, width, height) }
            .filter { it.width > 0 && it.height > 0 }
        if (content.width <= 0 || content.height <= 0 || memberBounds.isEmpty()) {
            return unmatched(groupIndex, Reason.UNMATCHED_NO_MODEL_BUBBLE)
        }

        val centerX = ((content.left + content.right - 1) / 2)
            .coerceIn(0, width - 1)
        val centerY = ((content.top + content.bottom - 1) / 2)
            .coerceIn(0, height - 1)
        val candidates = modelBubbles.mapIndexedNotNull { modelIndex, model ->
            val modelBounds = model.toIntRect(width, height)
            val instanceMask = instanceMasks[modelIndex]
            val contentBoxCoverage = intersectionArea(content, modelBounds).toFloat() /
                area(content).coerceAtLeast(1)
            val centerInsideBox = contains(modelBounds, centerX, centerY)
            if (!centerInsideBox && contentBoxCoverage < MIN_GEOMETRIC_CANDIDATE_COVERAGE) {
                return@mapIndexedNotNull null
            }

            val centerInsideMask = centerInsideBox && instanceMask.contains(centerX, centerY)
            val memberCoverage = memberMaskCoverage(
                mask = instanceMask,
                memberBounds = memberBounds,
                modelBounds = modelBounds,
            )
            val score = (
                memberCoverage * MEMBER_COVERAGE_WEIGHT +
                    contentBoxCoverage * BOX_COVERAGE_WEIGHT +
                    (if (centerInsideMask) CENTER_MASK_WEIGHT else 0f) +
                    model.confidence.coerceIn(0f, 1f) * MODEL_CONFIDENCE_WEIGHT
                ).coerceIn(0f, 1f)
            val acceptedReason = when {
                centerInsideMask &&
                    memberCoverage >= MIN_CENTER_MEMBER_COVERAGE &&
                    contentBoxCoverage >= MIN_CENTER_BOX_COVERAGE ->
                    Reason.MATCHED_CENTER_AND_COVERAGE

                memberCoverage >= MIN_MEMBER_COVERAGE &&
                    contentBoxCoverage >= MIN_BOX_COVERAGE ->
                    Reason.MATCHED_COVERAGE

                else -> null
            }
            Candidate(
                modelBubbleIndex = modelIndex,
                score = score,
                memberMaskCoverage = memberCoverage,
                contentBoxCoverage = contentBoxCoverage,
                centerInsideMask = centerInsideMask,
                acceptedReason = acceptedReason,
            )
        }.sortedByDescending { it.score }

        if (candidates.isEmpty()) {
            return unmatched(groupIndex, Reason.UNMATCHED_NO_MODEL_BUBBLE)
        }
        val accepted = candidates.filter { it.acceptedReason != null }
        if (accepted.isEmpty()) {
            val best = candidates.first()
            return Association(
                ocrGroupIndex = groupIndex,
                modelBubbleIndex = null,
                reason = Reason.UNMATCHED_LOW_COVERAGE,
                score = best.score,
                memberMaskCoverage = best.memberMaskCoverage,
                contentBoxCoverage = best.contentBoxCoverage,
                centerInsideMask = best.centerInsideMask,
            )
        }
        val best = accepted.first()
        val second = accepted.getOrNull(1)
        if (
            second != null &&
            best.centerInsideMask == second.centerInsideMask &&
            best.score - second.score <= AMBIGUOUS_SCORE_DELTA
        ) {
            return Association(
                ocrGroupIndex = groupIndex,
                modelBubbleIndex = null,
                reason = Reason.UNMATCHED_AMBIGUOUS,
                score = best.score,
                memberMaskCoverage = best.memberMaskCoverage,
                contentBoxCoverage = best.contentBoxCoverage,
                centerInsideMask = best.centerInsideMask,
            )
        }
        return Association(
            ocrGroupIndex = groupIndex,
            modelBubbleIndex = best.modelBubbleIndex,
            reason = checkNotNull(best.acceptedReason),
            score = best.score,
            memberMaskCoverage = best.memberMaskCoverage,
            contentBoxCoverage = best.contentBoxCoverage,
            centerInsideMask = best.centerInsideMask,
        )
    }

    private fun memberMaskCoverage(
        mask: BubbleSegmentationPostprocessor.InstanceMask,
        memberBounds: List<IntRect>,
        modelBounds: IntRect,
    ): Float {
        var memberPixels = 0L
        var coveredPixels = 0L
        memberBounds.forEach { member ->
            for (y in member.top until member.bottom) {
                for (x in member.left until member.right) {
                    memberPixels++
                    if (contains(modelBounds, x, y) && mask.contains(x, y)) coveredPixels++
                }
            }
        }
        return if (memberPixels > 0L) {
            coveredPixels.toFloat() / memberPixels
        } else {
            0f
        }
    }

    private fun BubbleSegmentationPostprocessor.Detection.toIntRect(
        width: Int,
        height: Int,
    ): IntRect = IntRect(
        left = floor(left).toInt().coerceIn(0, width),
        top = floor(top).toInt().coerceIn(0, height),
        right = ceil(right).toInt().coerceIn(0, width),
        bottom = ceil(bottom).toInt().coerceIn(0, height),
    )

    private fun intersectionArea(first: IntRect, second: IntRect): Long {
        val intersectionWidth = max(0, min(first.right, second.right) - max(first.left, second.left))
        val intersectionHeight = max(0, min(first.bottom, second.bottom) - max(first.top, second.top))
        return intersectionWidth.toLong() * intersectionHeight
    }

    private fun area(rect: IntRect): Long =
        rect.width.coerceAtLeast(0).toLong() * rect.height.coerceAtLeast(0)

    private fun contains(rect: IntRect, x: Int, y: Int): Boolean =
        x >= rect.left && x < rect.right && y >= rect.top && y < rect.bottom

    private fun clamp(rect: IntRect, width: Int, height: Int): IntRect = IntRect(
        left = rect.left.coerceIn(0, width),
        top = rect.top.coerceIn(0, height),
        right = rect.right.coerceIn(0, width),
        bottom = rect.bottom.coerceIn(0, height),
    )

    private fun unmatched(groupIndex: Int, reason: Reason): Association = Association(
        ocrGroupIndex = groupIndex,
        modelBubbleIndex = null,
        reason = reason,
        score = 0f,
        memberMaskCoverage = 0f,
        contentBoxCoverage = 0f,
        centerInsideMask = false,
    )

    private const val MIN_GEOMETRIC_CANDIDATE_COVERAGE = 0.25f
    private const val MIN_CENTER_MEMBER_COVERAGE = 0.50f
    private const val MIN_CENTER_BOX_COVERAGE = 0.45f
    private const val MIN_MEMBER_COVERAGE = 0.78f
    private const val MIN_BOX_COVERAGE = 0.65f
    private const val MEMBER_COVERAGE_WEIGHT = 0.55f
    private const val BOX_COVERAGE_WEIGHT = 0.20f
    private const val CENTER_MASK_WEIGHT = 0.20f
    private const val MODEL_CONFIDENCE_WEIGHT = 0.05f
    private const val AMBIGUOUS_SCORE_DELTA = 0.04f
}
