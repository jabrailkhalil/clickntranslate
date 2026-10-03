// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Pure Kotlin post-processing for a single-class YOLO segmentation export.
 *
 * The model adapter is deliberately independent from Ultralytics runtime code: Android only
 * consumes the two ONNX tensors and this class applies confidence filtering, NMS and mask
 * projection. Keeping it pure also makes the geometry and threshold policy table-testable.
 */
internal object BubbleSegmentationPostprocessor {

    data class Letterbox(
        val sourceWidth: Int,
        val sourceHeight: Int,
        val inputSize: Int,
        val scale: Float,
        val scaledWidth: Int,
        val scaledHeight: Int,
        val padLeft: Int,
        val padTop: Int,
    ) {
        companion object {
            fun create(sourceWidth: Int, sourceHeight: Int, inputSize: Int): Letterbox {
                require(sourceWidth > 0 && sourceHeight > 0 && inputSize > 0)
                val scale = min(
                    inputSize.toFloat() / sourceWidth,
                    inputSize.toFloat() / sourceHeight,
                )
                val scaledWidth = (sourceWidth * scale).roundToInt().coerceIn(1, inputSize)
                val scaledHeight = (sourceHeight * scale).roundToInt().coerceIn(1, inputSize)
                return Letterbox(
                    sourceWidth = sourceWidth,
                    sourceHeight = sourceHeight,
                    inputSize = inputSize,
                    scale = scale,
                    scaledWidth = scaledWidth,
                    scaledHeight = scaledHeight,
                    padLeft = (inputSize - scaledWidth) / 2,
                    padTop = (inputSize - scaledHeight) / 2,
                )
            }
        }
    }

    data class Detection(
        val confidence: Float,
        val left: Float,
        val top: Float,
        val right: Float,
        val bottom: Float,
        val maskCoefficients: FloatArray,
    )

    /**
     * Cropped mask for one retained model detection.
     *
     * Keeping only the detection crop avoids allocating one full-screen BooleanArray per bubble.
     * Coordinates use the same half-open convention as image pixel loops.
     */
    data class InstanceMask(
        val left: Int,
        val top: Int,
        val width: Int,
        val height: Int,
        val pixels: BooleanArray,
    ) {
        init {
            require(width >= 0 && height >= 0)
            require(pixels.size == width * height)
        }

        val right: Int
            get() = left + width

        val bottom: Int
            get() = top + height

        fun contains(x: Int, y: Int): Boolean =
            x >= left &&
                x < right &&
                y >= top &&
                y < bottom &&
                pixels[(y - top) * width + (x - left)]
    }

    data class Result(
        val detections: List<Detection>,
        val instanceMasks: List<InstanceMask>,
        val unionMask: BooleanArray,
    )

    fun process(
        detectionOutput: FloatArray,
        anchorCount: Int,
        prototypeOutput: FloatArray,
        prototypeWidth: Int,
        prototypeHeight: Int,
        maskChannelCount: Int,
        letterbox: Letterbox,
        confidenceThreshold: Float = DEFAULT_CONFIDENCE_THRESHOLD,
        iouThreshold: Float = DEFAULT_IOU_THRESHOLD,
        maskThresholdLogit: Float = DEFAULT_MASK_THRESHOLD_LOGIT,
        maxDetections: Int = DEFAULT_MAX_DETECTIONS,
    ): Result {
        require(anchorCount > 0)
        require(prototypeWidth > 0 && prototypeHeight > 0 && maskChannelCount > 0)
        require(detectionOutput.size == (BOX_CHANNELS + CLASS_CHANNELS + maskChannelCount) * anchorCount)
        require(prototypeOutput.size == maskChannelCount * prototypeWidth * prototypeHeight)

        val candidates = decodeDetections(
            detectionOutput = detectionOutput,
            anchorCount = anchorCount,
            maskChannelCount = maskChannelCount,
            letterbox = letterbox,
            confidenceThreshold = confidenceThreshold,
        )
        val retained = nonMaxSuppression(candidates, iouThreshold, maxDetections)
        val unionMask = BooleanArray(letterbox.sourceWidth * letterbox.sourceHeight)
        val instanceMasks = retained.map { detection ->
            projectMask(
                unionOutput = unionMask,
                detection = detection,
                prototypeOutput = prototypeOutput,
                prototypeWidth = prototypeWidth,
                prototypeHeight = prototypeHeight,
                maskChannelCount = maskChannelCount,
                letterbox = letterbox,
                maskThresholdLogit = maskThresholdLogit,
            )
        }
        return Result(
            detections = retained,
            instanceMasks = instanceMasks,
            unionMask = unionMask,
        )
    }

    internal fun decodeDetections(
        detectionOutput: FloatArray,
        anchorCount: Int,
        maskChannelCount: Int,
        letterbox: Letterbox,
        confidenceThreshold: Float,
    ): List<Detection> {
        val candidates = ArrayList<Detection>()
        for (anchor in 0 until anchorCount) {
            val confidence = detectionOutput[channelOffset(CLASS_SCORE_CHANNEL, anchorCount) + anchor]
            if (!confidence.isFinite() || confidence < confidenceThreshold) continue

            val centerX = detectionOutput[channelOffset(0, anchorCount) + anchor]
            val centerY = detectionOutput[channelOffset(1, anchorCount) + anchor]
            val width = detectionOutput[channelOffset(2, anchorCount) + anchor]
            val height = detectionOutput[channelOffset(3, anchorCount) + anchor]
            if (
                !centerX.isFinite() || !centerY.isFinite() ||
                !width.isFinite() || !height.isFinite() ||
                width <= 0f || height <= 0f
            ) {
                continue
            }

            val left = ((centerX - width / 2f) - letterbox.padLeft) / letterbox.scale
            val top = ((centerY - height / 2f) - letterbox.padTop) / letterbox.scale
            val right = ((centerX + width / 2f) - letterbox.padLeft) / letterbox.scale
            val bottom = ((centerY + height / 2f) - letterbox.padTop) / letterbox.scale
            val clippedLeft = left.coerceIn(0f, letterbox.sourceWidth.toFloat())
            val clippedTop = top.coerceIn(0f, letterbox.sourceHeight.toFloat())
            val clippedRight = right.coerceIn(0f, letterbox.sourceWidth.toFloat())
            val clippedBottom = bottom.coerceIn(0f, letterbox.sourceHeight.toFloat())
            if (clippedRight - clippedLeft < MIN_BOX_SIDE || clippedBottom - clippedTop < MIN_BOX_SIDE) {
                continue
            }

            val coefficients = FloatArray(maskChannelCount) { channel ->
                detectionOutput[
                    channelOffset(BOX_CHANNELS + CLASS_CHANNELS + channel, anchorCount) + anchor
                ]
            }
            candidates += Detection(
                confidence = confidence,
                left = clippedLeft,
                top = clippedTop,
                right = clippedRight,
                bottom = clippedBottom,
                maskCoefficients = coefficients,
            )
        }
        return candidates
    }

    internal fun nonMaxSuppression(
        candidates: List<Detection>,
        iouThreshold: Float,
        maxDetections: Int,
    ): List<Detection> {
        if (candidates.isEmpty() || maxDetections <= 0) return emptyList()
        val retained = ArrayList<Detection>(min(candidates.size, maxDetections))
        candidates.sortedByDescending { it.confidence }.forEach { candidate ->
            if (retained.size >= maxDetections) return@forEach
            if (retained.none { kept -> intersectionOverUnion(candidate, kept) > iouThreshold }) {
                retained += candidate
            }
        }
        return retained
    }

    private fun projectMask(
        unionOutput: BooleanArray,
        detection: Detection,
        prototypeOutput: FloatArray,
        prototypeWidth: Int,
        prototypeHeight: Int,
        maskChannelCount: Int,
        letterbox: Letterbox,
        maskThresholdLogit: Float,
    ): InstanceMask {
        val prototypePlaneSize = prototypeWidth * prototypeHeight
        val logits = FloatArray(prototypePlaneSize)
        for (channel in 0 until maskChannelCount) {
            val coefficient = detection.maskCoefficients[channel]
            if (coefficient == 0f) continue
            val channelOffset = channel * prototypePlaneSize
            for (index in 0 until prototypePlaneSize) {
                logits[index] += coefficient * prototypeOutput[channelOffset + index]
            }
        }

        val left = detection.left.toInt().coerceIn(0, letterbox.sourceWidth)
        val top = detection.top.toInt().coerceIn(0, letterbox.sourceHeight)
        val right = kotlin.math.ceil(detection.right.toDouble()).toInt()
            .coerceIn(0, letterbox.sourceWidth)
        val bottom = kotlin.math.ceil(detection.bottom.toDouble()).toInt()
            .coerceIn(0, letterbox.sourceHeight)
        val maskWidth = (right - left).coerceAtLeast(0)
        val maskHeight = (bottom - top).coerceAtLeast(0)
        val pixels = BooleanArray(maskWidth * maskHeight)
        for (sourceY in top until bottom) {
            val modelY = (sourceY + 0.5f) * letterbox.scale + letterbox.padTop
            val prototypeY = modelY * prototypeHeight / letterbox.inputSize - 0.5f
            val outputRow = sourceY * letterbox.sourceWidth
            val instanceRow = (sourceY - top) * maskWidth
            for (sourceX in left until right) {
                val modelX = (sourceX + 0.5f) * letterbox.scale + letterbox.padLeft
                val prototypeX = modelX * prototypeWidth / letterbox.inputSize - 0.5f
                if (
                    bilinearSample(
                        values = logits,
                        width = prototypeWidth,
                        height = prototypeHeight,
                        x = prototypeX,
                        y = prototypeY,
                    ) > maskThresholdLogit
                ) {
                    unionOutput[outputRow + sourceX] = true
                    pixels[instanceRow + sourceX - left] = true
                }
            }
        }
        return InstanceMask(
            left = left,
            top = top,
            width = maskWidth,
            height = maskHeight,
            pixels = pixels,
        )
    }

    internal fun bilinearSample(
        values: FloatArray,
        width: Int,
        height: Int,
        x: Float,
        y: Float,
    ): Float {
        require(width > 0 && height > 0 && values.size == width * height)
        val clippedX = x.coerceIn(0f, (width - 1).toFloat())
        val clippedY = y.coerceIn(0f, (height - 1).toFloat())
        val x0 = clippedX.toInt()
        val y0 = clippedY.toInt()
        val x1 = min(x0 + 1, width - 1)
        val y1 = min(y0 + 1, height - 1)
        val xWeight = clippedX - x0
        val yWeight = clippedY - y0
        val top = values[y0 * width + x0] * (1f - xWeight) +
            values[y0 * width + x1] * xWeight
        val bottom = values[y1 * width + x0] * (1f - xWeight) +
            values[y1 * width + x1] * xWeight
        return top * (1f - yWeight) + bottom * yWeight
    }

    private fun intersectionOverUnion(first: Detection, second: Detection): Float {
        val intersectionWidth = max(0f, min(first.right, second.right) - max(first.left, second.left))
        val intersectionHeight = max(0f, min(first.bottom, second.bottom) - max(first.top, second.top))
        val intersection = intersectionWidth * intersectionHeight
        if (intersection <= 0f) return 0f
        val firstArea = (first.right - first.left) * (first.bottom - first.top)
        val secondArea = (second.right - second.left) * (second.bottom - second.top)
        val union = firstArea + secondArea - intersection
        return if (union > 0f) intersection / union else 0f
    }

    private fun channelOffset(channel: Int, anchorCount: Int): Int = channel * anchorCount

    const val DEFAULT_CONFIDENCE_THRESHOLD = 0.35f
    const val DEFAULT_IOU_THRESHOLD = 0.45f
    const val DEFAULT_MASK_THRESHOLD_LOGIT = 0f
    const val DEFAULT_MAX_DETECTIONS = 64
    private const val BOX_CHANNELS = 4
    private const val CLASS_CHANNELS = 1
    private const val CLASS_SCORE_CHANNEL = 4
    private const val MIN_BOX_SIDE = 2f
}
