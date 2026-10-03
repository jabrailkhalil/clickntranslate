// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BubbleSegmentationPostprocessorTest {

    private data class DecodeCase(
        val name: String,
        val boxes: List<BoxInput>,
        val expectedConfidences: List<Float>,
    )

    private data class BoxInput(
        val centerX: Float,
        val centerY: Float,
        val width: Float,
        val height: Float,
        val confidence: Float,
    )

    @Test
    fun process_tableDriven_filtersConfidenceAndSuppressesOverlaps() {
        val cases = listOf(
            DecodeCase(
                name = "below confidence is discarded",
                boxes = listOf(BoxInput(50f, 50f, 40f, 40f, 0.34f)),
                expectedConfidences = emptyList(),
            ),
            DecodeCase(
                name = "overlap keeps higher confidence",
                boxes = listOf(
                    BoxInput(50f, 50f, 40f, 40f, 0.92f),
                    BoxInput(52f, 50f, 40f, 40f, 0.73f),
                ),
                expectedConfidences = listOf(0.92f),
            ),
            DecodeCase(
                name = "separate bubbles remain",
                boxes = listOf(
                    BoxInput(25f, 25f, 20f, 20f, 0.61f),
                    BoxInput(75f, 75f, 20f, 20f, 0.88f),
                ),
                expectedConfidences = listOf(0.88f, 0.61f),
            ),
        )

        cases.forEach { case ->
            val anchorCount = case.boxes.size
            val detectionOutput = detectionTensor(case.boxes, maskCoefficient = 1f)
            val result = BubbleSegmentationPostprocessor.process(
                detectionOutput = detectionOutput,
                anchorCount = anchorCount,
                prototypeOutput = FloatArray(4 * 4) { 1f },
                prototypeWidth = 4,
                prototypeHeight = 4,
                maskChannelCount = 1,
                letterbox = BubbleSegmentationPostprocessor.Letterbox.create(100, 100, 100),
            )

            assertEquals(
                case.name,
                case.expectedConfidences,
                result.detections.map { it.confidence },
            )
        }
    }

    @Test
    fun process_tableDriven_projectsLetterboxAndMaskThreshold() {
        data class MaskCase(
            val name: String,
            val coefficient: Float,
            val expectedCenter: Boolean,
        )
        val cases = listOf(
            MaskCase("positive logit fills detection", coefficient = 1f, expectedCenter = true),
            MaskCase("zero logit is excluded by strict threshold", coefficient = 0f, expectedCenter = false),
            MaskCase("negative logit is excluded", coefficient = -1f, expectedCenter = false),
        )
        val letterbox = BubbleSegmentationPostprocessor.Letterbox.create(
            sourceWidth = 200,
            sourceHeight = 100,
            inputSize = 100,
        )
        assertEquals(50, letterbox.scaledHeight)
        assertEquals(25, letterbox.padTop)

        cases.forEach { case ->
            val modelBox = BoxInput(
                centerX = 50f,
                centerY = 50f,
                width = 40f,
                height = 20f,
                confidence = 0.9f,
            )
            val result = BubbleSegmentationPostprocessor.process(
                detectionOutput = detectionTensor(listOf(modelBox), case.coefficient),
                anchorCount = 1,
                prototypeOutput = FloatArray(4 * 4) { 1f },
                prototypeWidth = 4,
                prototypeHeight = 4,
                maskChannelCount = 1,
                letterbox = letterbox,
            )

            val detection = result.detections.single()
            assertEquals("${case.name}: left", 60f, detection.left, 0.001f)
            assertEquals("${case.name}: top", 30f, detection.top, 0.001f)
            assertEquals("${case.name}: right", 140f, detection.right, 0.001f)
            assertEquals("${case.name}: bottom", 70f, detection.bottom, 0.001f)
            assertEquals(
                "${case.name}: center",
                case.expectedCenter,
                result.unionMask[50 * 200 + 100],
            )
            assertEquals("${case.name}: one instance mask", 1, result.instanceMasks.size)
            assertEquals(
                "${case.name}: instance center",
                case.expectedCenter,
                result.instanceMasks.single().contains(100, 50),
            )
            assertFalse(
                "${case.name}: instance excludes outside box",
                result.instanceMasks.single().contains(5, 5),
            )
            assertFalse("${case.name}: outside box", result.unionMask[5 * 200 + 5])
        }
    }

    @Test
    fun process_tableDriven_keepsMasksSeparatedWhileBuildingUnion() {
        data class InstanceCase(
            val name: String,
            val x: Int,
            val y: Int,
            val expectedInstances: List<Boolean>,
            val expectedUnion: Boolean,
        )
        val boxes = listOf(
            BoxInput(25f, 50f, 20f, 20f, 0.9f),
            BoxInput(75f, 50f, 20f, 20f, 0.8f),
        )
        val result = BubbleSegmentationPostprocessor.process(
            detectionOutput = detectionTensor(boxes, maskCoefficient = 1f),
            anchorCount = boxes.size,
            prototypeOutput = FloatArray(4 * 4) { 1f },
            prototypeWidth = 4,
            prototypeHeight = 4,
            maskChannelCount = 1,
            letterbox = BubbleSegmentationPostprocessor.Letterbox.create(100, 100, 100),
        )
        val cases = listOf(
            InstanceCase("first bubble", 25, 50, listOf(true, false), true),
            InstanceCase("second bubble", 75, 50, listOf(false, true), true),
            InstanceCase("background", 50, 10, listOf(false, false), false),
        )

        assertEquals(2, result.instanceMasks.size)
        cases.forEach { case ->
            assertEquals(
                "${case.name}: instances",
                case.expectedInstances,
                result.instanceMasks.map { it.contains(case.x, case.y) },
            )
            assertEquals(
                "${case.name}: union",
                case.expectedUnion,
                result.unionMask[case.y * 100 + case.x],
            )
        }
    }

    @Test
    fun process_capsDetectionsAfterNms() {
        val boxes = (0 until 8).map { index ->
            BoxInput(
                centerX = 8f + index * 11f,
                centerY = 50f,
                width = 6f,
                height = 6f,
                confidence = 0.5f + index * 0.01f,
            )
        }
        val result = BubbleSegmentationPostprocessor.process(
            detectionOutput = detectionTensor(boxes, maskCoefficient = 1f),
            anchorCount = boxes.size,
            prototypeOutput = FloatArray(4 * 4) { 1f },
            prototypeWidth = 4,
            prototypeHeight = 4,
            maskChannelCount = 1,
            letterbox = BubbleSegmentationPostprocessor.Letterbox.create(100, 100, 100),
            maxDetections = 3,
        )

        assertEquals(3, result.detections.size)
        assertTrue(result.detections.zipWithNext().all { (first, second) ->
            first.confidence >= second.confidence
        })
    }

    @Test
    fun bilinearSample_tableDriven_interpolatesCornersEdgesAndCenter() {
        data class SampleCase(
            val name: String,
            val x: Float,
            val y: Float,
            val expected: Float,
        )
        val values = floatArrayOf(
            0f, 2f,
            4f, 6f,
        )
        val cases = listOf(
            SampleCase("top left", 0f, 0f, 0f),
            SampleCase("top edge midpoint", 0.5f, 0f, 1f),
            SampleCase("center", 0.5f, 0.5f, 3f),
            SampleCase("bottom right", 1f, 1f, 6f),
            SampleCase("coordinates clamp outside", 2f, -1f, 2f),
        )

        cases.forEach { case ->
            assertEquals(
                case.name,
                case.expected,
                BubbleSegmentationPostprocessor.bilinearSample(
                    values = values,
                    width = 2,
                    height = 2,
                    x = case.x,
                    y = case.y,
                ),
                0.0001f,
            )
        }
    }

    private fun detectionTensor(
        boxes: List<BoxInput>,
        maskCoefficient: Float,
    ): FloatArray {
        val anchors = boxes.size
        val output = FloatArray((4 + 1 + 1) * anchors)
        boxes.forEachIndexed { index, box ->
            output[0 * anchors + index] = box.centerX
            output[1 * anchors + index] = box.centerY
            output[2 * anchors + index] = box.width
            output[3 * anchors + index] = box.height
            output[4 * anchors + index] = box.confidence
            output[5 * anchors + index] = maskCoefficient
        }
        return output
    }
}
