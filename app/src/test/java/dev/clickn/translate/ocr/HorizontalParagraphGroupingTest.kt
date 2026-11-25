// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import org.junit.Assert.assertEquals
import org.junit.Test

class HorizontalParagraphGroupingTest {

    private data class Case(
        val name: String,
        val rects: List<MergeDebugRect>,
        val bubbleGroupIds: List<Int?> = List(rects.size) { null },
        val expectedGroups: List<List<Int>>,
    )

    @Test
    fun groupHorizontalParagraphRects_tableDriven_preservesDenseReadingOrderWithoutOverlapSplits() {
        val cases = listOf(
            Case(
                name = "ordinary separated paragraph",
                rects = listOf(
                    MergeDebugRect(10, 10, 210, 60),
                    MergeDebugRect(12, 70, 230, 120),
                    MergeDebugRect(8, 130, 190, 180),
                ),
                expectedGroups = listOf(listOf(0, 1, 2)),
            ),
            Case(
                name = "latest dense score table does not split odd and even rows",
                rects = listOf(
                    MergeDebugRect(276, 1650, 488, 1737),
                    MergeDebugRect(189, 1690, 399, 1783),
                    MergeDebugRect(189, 1750, 539, 1847),
                    MergeDebugRect(182, 1806, 360, 1884),
                    MergeDebugRect(178, 1858, 354, 1937),
                    MergeDebugRect(168, 1908, 348, 1993),
                    MergeDebugRect(163, 1961, 342, 2044),
                    MergeDebugRect(156, 2014, 335, 2094),
                    MergeDebugRect(147, 2066, 329, 2148),
                ),
                expectedGroups = listOf((0..8).toList()),
            ),
            Case(
                name = "same row independent labels remain separate",
                rects = listOf(
                    MergeDebugRect(10, 10, 110, 60),
                    MergeDebugRect(150, 12, 260, 62),
                ),
                expectedGroups = listOf(listOf(0), listOf(1)),
            ),
            Case(
                name = "large vertical gap remains separate",
                rects = listOf(
                    MergeDebugRect(10, 10, 210, 60),
                    MergeDebugRect(12, 180, 230, 230),
                ),
                expectedGroups = listOf(listOf(0), listOf(1)),
            ),
            Case(
                name = "different detected bubbles remain separate despite intersecting boxes",
                rects = listOf(
                    MergeDebugRect(10, 10, 220, 150),
                    MergeDebugRect(20, 80, 210, 210),
                ),
                bubbleGroupIds = listOf(4, 7),
                expectedGroups = listOf(listOf(0), listOf(1)),
            ),
            Case(
                name = "detected bubble does not absorb unmatched nearby text",
                rects = listOf(
                    MergeDebugRect(10, 10, 220, 150),
                    MergeDebugRect(20, 120, 210, 220),
                ),
                bubbleGroupIds = listOf(4, null),
                expectedGroups = listOf(listOf(0), listOf(1)),
            ),
        )

        cases.forEach { case ->
            assertEquals(
                case.name,
                case.expectedGroups,
                groupHorizontalParagraphRects(
                    rects = case.rects,
                    bubbleGroupIds = case.bubbleGroupIds,
                    verticalGapRatio = 0.8f,
                    horizontalOverlapRatio = 0.3f,
                ),
            )
        }
    }

    @Test
    fun standard_groupsRecordedSourceDebugWrapsWithoutJoiningParagraphsOrFixtureChrome() {
        // Actual restored-source API36 capture#1, 2026-10-25 18:53:15, ML_KIT_AUTO.
        // .tmp/archive-restore/41-source-debug-capture-log.txt:55-61, raw-no-merge #1-7.
        // The fixture's TextView contains two paragraphs separated by a real blank line.
        val observed = listOf(
            MergeDebugRect(200, 45, 338, 82),     // System sharing timer.
            MergeDebugRect(48, 962, 320, 1006),   // Touch counter.
            MergeDebugRect(50, 1037, 227, 1065),  // Fixture UID label.
            MergeDebugRect(53, 1094, 880, 1155),  // Bright rivers run through quiet
            MergeDebugRect(49, 1168, 249, 1228),  // valleys.
            MergeDebugRect(64, 1312, 855, 1371),  // The small orange fox reads a
            MergeDebugRect(51, 1382, 382, 1437),  // useful book.
        )
        assertEquals(
            "The two sentence wraps must become two independent paragraph groups",
            listOf(listOf(0), listOf(1), listOf(2), listOf(3, 4), listOf(5, 6)),
            standard(observed),
        )
    }

    @Test
    fun standard_keepsTwoWrappedColumnsIndependentWithInterleavedDetectorOrder() {
        // Constructed two-column layout, each column containing one two-line paragraph. Detector order
        // is deliberately interleaved; equal-height rows in another column are not continuations.
        val observed = listOf(
            MergeDebugRect(355, 48, 490, 78),  // Right paragraph, second line.
            MergeDebugRect(10, 10, 210, 40),   // Left paragraph, first line.
            MergeDebugRect(350, 12, 610, 42),  // Right paragraph, first line.
            MergeDebugRect(10, 46, 100, 76),   // Left paragraph, second line.
        )
        assertEquals(listOf(listOf(1, 3), listOf(2, 0)), standard(observed))
    }

    @Test
    fun standard_groupsTwoRightAlignedRtlLinesInTopToBottomOrder() {
        // Constructed geometry contract only: the second logical Arabic/Hebrew line is shorter and
        // right-aligned. This grouper has no text/direction input and does not reorder glyphs
        // or choose reading order between independent RTL columns.
        val observed = listOf(
            MergeDebugRect(420, 148, 600, 188), // Second logical line.
            MergeDebugRect(240, 100, 600, 140), // First logical line.
        )
        assertEquals(listOf(listOf(1, 0)), standard(observed))
    }

    private fun standard(rects: List<MergeDebugRect>): List<List<Int>> = groupHorizontalParagraphRects(
        rects = rects,
        bubbleGroupIds = List(rects.size) { null },
        verticalGapRatio = 0.8f,
        horizontalOverlapRatio = 0.3f,
    )
}
