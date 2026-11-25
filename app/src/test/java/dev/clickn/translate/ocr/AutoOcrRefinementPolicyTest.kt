package dev.clickn.translate.ocr

import org.junit.Assert.*
import org.junit.Test

class AutoOcrRefinementPolicyTest {
    private data class Region(
        val text: String,
        val box: MergeDebugRect,
        val sources: List<MergeDebugRect> = listOf(box),
        val language: String = "en",
        val confidence: Float = .91f,
    )

    @Test fun wholeParagraphRefinesToBothLinesButNeverToOnlyItsLongPrefix() {
        // Actual lost source has 34 letters; its long prefix has 27 and its tail has 7.
        // Prefix geometry is from final-debug-capture.log:1542; tail/container are
        // constructed, separate line boxes to exercise the paragraph-vs-lines contract.
        val prefix = Region("Bright rivers run through quiet", MergeDebugRect(16, 14, 832, 76))
        val tail = Region("valleys.", MergeDebugRect(4, 88, 204, 148), confidence = .883f)
        val original = Region(prefix.text + "\n" + tail.text, MergeDebugRect(4, 14, 832, 148),
            listOf(prefix.box, tail.box), confidence = .966f)
        assertEquals(34, original.text.count(Char::isLetter))
        assertEquals(27, prefix.text.count(Char::isLetter))
        assertEquals(7, tail.text.count(Char::isLetter))
        for (lines in listOf(listOf(prefix, tail), listOf(tail, prefix))) {
            val usable = accept(listOf(original), lines)
            assertEquals(setOf(prefix, tail), usable.toSet())
            assertEquals(setOf(prefix, tail), replace(listOf(original), usable).toSet())
        }
        val partial = accept(listOf(original), listOf(prefix))
        assertTrue("A 27-letter prefix must not erase a complete 34-letter paragraph", partial.isEmpty())
        assertEquals(listOf(original), replace(listOf(original), partial))
        val noTailGeometry = original.copy(sources = listOf(prefix.box))
        assertTrue("Text length alone cannot prove the final source line was covered",
            accept(listOf(original), listOf(noTailGeometry)).isEmpty())
    }

    @Test fun independentColumnStillRefinesWhileIncompleteOrForeignLanguageComponentsStayIntact() {
        val left = Region("Bright rivers run through quiet\nvalleys.", MergeDebugRect(0, 0, 800, 150),
            listOf(MergeDebugRect(0, 0, 800, 60), MergeDebugRect(0, 90, 200, 150)))
        val prefix = Region("Bright rivers run through quiet", left.sources.first())
        val right = Region("The small orange fox reads a useful book.", MergeDebugRect(900, 0, 1500, 150))
        val betterRight = right.copy(confidence = .99f)
        val usable = accept(listOf(left, right), listOf(prefix, betterRight))
        assertEquals(listOf(betterRight), usable)
        assertEquals(listOf(left, betterRight), replace(listOf(left, right), usable))

        val arabic = right.copy(text = "مرحبا بالعالم", language = "ar")
        val overWideEnglish = left.copy(box = MergeDebugRect(0, 0, 1500, 150),
            sources = listOf(MergeDebugRect(0, 0, 1500, 150)))
        assertTrue("Refinement must not delete an overlapping independent Arabic region",
            accept(listOf(left, arabic), listOf(overWideEnglish)).isEmpty())
        assertFalse("Overlapping fragments must not count the same coverage twice",
            coversAutoOcrSourceRects(listOf(MergeDebugRect(0, 0, 100, 100)),
                listOf(MergeDebugRect(0, 0, 25, 100), MergeDebugRect(0, 0, 25, 100))))
        assertTrue(coversAutoOcrSourceRects(listOf(MergeDebugRect(0, 0, 100, 100)),
            listOf(MergeDebugRect(0, 0, 30, 100), MergeDebugRect(30, 0, 60, 100))))
    }

    private fun accept(old: List<Region>, next: List<Region>): List<Region> = completeAutoOcrRefinements(
        old, next, "en", { AutoOcrEvidence(it.text, it.language, it.confidence) }, ::overlaps,
        { region, replacements -> coversAutoOcrSourceRects(region.sources, replacements.flatMap { it.sources }) },
    )

    private fun replace(old: List<Region>, next: List<Region>): List<Region> =
        replaceAutoOcrRegions(old, next, "en", { it.language }, ::overlaps)

    private fun overlaps(a: Region, b: Region): Boolean =
        minOf(a.box.right, b.box.right) > maxOf(a.box.left, b.box.left) &&
            minOf(a.box.bottom, b.box.bottom) > maxOf(a.box.top, b.box.top)
}
