// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import dev.clickn.translate.ocr.BubbleClusterer.IntRect
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BubbleMaskAssociatorTest {

    private data class AssociationCase(
        val name: String,
        val modelBounds: List<IntRect>,
        val maskedBounds: List<IntRect>,
        val group: BubbleMaskAssociator.OcrGroup,
        val expectedModelIndex: Int?,
        val expectedReason: BubbleMaskAssociator.Reason,
    )

    @Test
    fun associate_tableDriven_matchesOnlyWithGeometricAndMaskEvidence() {
        val cases = listOf(
            AssociationCase(
                name = "center and members inside one bubble",
                modelBounds = listOf(IntRect(20, 20, 80, 80)),
                maskedBounds = listOf(IntRect(20, 20, 80, 80)),
                group = group(40, 35, 60, 65),
                expectedModelIndex = 0,
                expectedReason = BubbleMaskAssociator.Reason.MATCHED_CENTER_AND_COVERAGE,
            ),
            AssociationCase(
                name = "model box without mask evidence is rejected",
                modelBounds = listOf(IntRect(20, 20, 80, 80)),
                maskedBounds = emptyList(),
                group = group(40, 35, 60, 65),
                expectedModelIndex = null,
                expectedReason = BubbleMaskAssociator.Reason.UNMATCHED_LOW_COVERAGE,
            ),
            AssociationCase(
                name = "distant sound effect has no candidate",
                modelBounds = listOf(IntRect(20, 20, 50, 50)),
                maskedBounds = listOf(IntRect(20, 20, 50, 50)),
                group = group(75, 70, 95, 95),
                expectedModelIndex = null,
                expectedReason = BubbleMaskAssociator.Reason.UNMATCHED_NO_MODEL_BUBBLE,
            ),
            AssociationCase(
                name = "best of separate bubbles is selected",
                modelBounds = listOf(
                    IntRect(5, 5, 45, 95),
                    IntRect(55, 5, 95, 95),
                ),
                maskedBounds = listOf(
                    IntRect(5, 5, 45, 95),
                    IntRect(55, 5, 95, 95),
                ),
                group = group(64, 30, 84, 70),
                expectedModelIndex = 1,
                expectedReason = BubbleMaskAssociator.Reason.MATCHED_CENTER_AND_COVERAGE,
            ),
            AssociationCase(
                name = "equally supported overlapping bubbles are ambiguous",
                modelBounds = listOf(
                    IntRect(15, 15, 85, 85),
                    IntRect(15, 15, 85, 85),
                ),
                maskedBounds = listOf(IntRect(15, 15, 85, 85)),
                group = group(40, 35, 60, 65),
                expectedModelIndex = null,
                expectedReason = BubbleMaskAssociator.Reason.UNMATCHED_AMBIGUOUS,
            ),
        )

        cases.forEach { case ->
            val result = BubbleMaskAssociator.associate(
                width = WIDTH,
                height = HEIGHT,
                modelBubbles = case.modelBounds.mapIndexed { index, bounds ->
                    detection(bounds, confidence = 0.95f - index * 0.02f)
                },
                instanceMasks = case.modelBounds.map { bounds ->
                    instanceMask(bounds, case.maskedBounds)
                },
                ocrGroups = listOf(case.group),
            ).single()

            assertEquals(case.name, case.expectedModelIndex, result.modelBubbleIndex)
            assertEquals(case.name, case.expectedReason, result.reason)
            assertEquals(case.name, case.expectedModelIndex != null, result.matched)
        }
    }

    @Test
    fun associate_allowsMultipleOcrGroupsToShareOneModelBubble() {
        val modelBounds = IntRect(10, 10, 90, 90)
        val results = BubbleMaskAssociator.associate(
            width = WIDTH,
            height = HEIGHT,
            modelBubbles = listOf(detection(modelBounds)),
            instanceMasks = listOf(instanceMask(modelBounds, listOf(modelBounds))),
            ocrGroups = listOf(
                group(25, 20, 45, 45),
                group(55, 50, 75, 75),
            ),
        )

        assertEquals(2, results.size)
        assertTrue(results.all { it.matched })
        assertTrue(results.all { it.modelBubbleIndex == 0 })
        assertFalse(results.any { it.reason == BubbleMaskAssociator.Reason.UNMATCHED_AMBIGUOUS })
    }

    @Test
    fun associate_tableDriven_individualMembersSeparateBubbleTextFromNearbyEffect() {
        val modelBounds = IntRect(10, 10, 60, 90)
        val speechText = IntRect(20, 20, 40, 60)
        val nearbyEffect = IntRect(55, 20, 90, 60)
        val modelBubbles = listOf(detection(modelBounds))
        val instanceMasks = listOf(instanceMask(modelBounds, listOf(modelBounds)))

        val cases = listOf(
            Triple(
                "pre-clustered mixed group safely falls back",
                listOf(
                    BubbleMaskAssociator.OcrGroup(
                        contentBounds = IntRect(20, 20, 90, 60),
                        memberBounds = listOf(speechText, nearbyEffect),
                    )
                ),
                listOf<Int?>(null),
            ),
            Triple(
                "individual members retain only speech bubble text",
                listOf(
                    BubbleMaskAssociator.OcrGroup(speechText, listOf(speechText)),
                    BubbleMaskAssociator.OcrGroup(nearbyEffect, listOf(nearbyEffect)),
                ),
                listOf(0, null),
            ),
        )

        cases.forEach { (name, groups, expectedModelIndices) ->
            val results = BubbleMaskAssociator.associate(
                width = WIDTH,
                height = HEIGHT,
                modelBubbles = modelBubbles,
                instanceMasks = instanceMasks,
                ocrGroups = groups,
            )
            assertEquals(name, expectedModelIndices, results.map { it.modelBubbleIndex })
        }
    }

    private fun group(
        left: Int,
        top: Int,
        right: Int,
        bottom: Int,
    ): BubbleMaskAssociator.OcrGroup {
        val bounds = IntRect(left, top, right, bottom)
        return BubbleMaskAssociator.OcrGroup(
            contentBounds = bounds,
            memberBounds = listOf(bounds),
        )
    }

    private fun detection(
        bounds: IntRect,
        confidence: Float = 0.95f,
    ): BubbleSegmentationPostprocessor.Detection =
        BubbleSegmentationPostprocessor.Detection(
            confidence = confidence,
            left = bounds.left.toFloat(),
            top = bounds.top.toFloat(),
            right = bounds.right.toFloat(),
            bottom = bounds.bottom.toFloat(),
            maskCoefficients = FloatArray(0),
        )

    private fun instanceMask(
        modelBounds: IntRect,
        maskedBounds: List<IntRect>,
    ): BubbleSegmentationPostprocessor.InstanceMask {
        val pixels = BooleanArray(modelBounds.width * modelBounds.height)
        for (y in modelBounds.top until modelBounds.bottom) {
            for (x in modelBounds.left until modelBounds.right) {
                if (maskedBounds.any { bounds ->
                        x >= bounds.left && x < bounds.right &&
                            y >= bounds.top && y < bounds.bottom
                    }
                ) {
                    pixels[(y - modelBounds.top) * modelBounds.width + x - modelBounds.left] = true
                }
            }
        }
        return BubbleSegmentationPostprocessor.InstanceMask(
            left = modelBounds.left,
            top = modelBounds.top,
            width = modelBounds.width,
            height = modelBounds.height,
            pixels = pixels,
        )
    }

    private companion object {
        const val WIDTH = 100
        const val HEIGHT = 100
    }
}
