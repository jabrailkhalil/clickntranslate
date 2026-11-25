// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import android.graphics.Rect
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.ocr.TextBlock
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Test

class PageTranslationPresentationTextPolicyTest {
    @Test
    fun floatingSingleLineText_tableDriven_normalizesEveryLineBreakForm() {
        data class Case(val name: String, val source: String, val expected: String)

        listOf(
            Case("unchanged single line", "  keep spacing  ", "  keep spacing  "),
            Case("Japanese joins without a space", "実際の授業では\n筆記音に", "実際の授業では筆記音に"),
            Case("Chinese blank line joins", "第一句\r\n\r\n第二句", "第一句第二句"),
            Case("Latin words keep a boundary", "hello\nworld", "hello world"),
            Case("Latin surrounding spaces collapse", "hello  \r\n  world", "hello world"),
            Case("Greek words keep a boundary", "καλή\rμέρα", "καλή μέρα"),
            Case("digits keep a boundary", "Level 1\n2026", "Level 1 2026"),
            Case("Latin punctuation keeps a boundary", "Hello,\nworld!", "Hello, world!"),
            Case("only line breaks becomes empty", "\r\n\n", ""),
        ).forEach { case ->
            assertEquals(case.name, case.expected, FloatingWindowSingleLineTextPolicy.normalize(case.source))
        }
    }

    @Test
    fun pageUnits_tableDriven_prepareSoftWrapsForBothPresentations() {
        data class Case(
            val presentation: RenderMode,
            val expected: List<String>,
        )

        val blocks = listOf(
            block("教室では\n聞こえない", 10),
            block("two\nwords", 90),
        )
        listOf(
            Case(RenderMode.BLOCKS, listOf("教室では聞こえない", "two words")),
            Case(RenderMode.FLOATING_WINDOW, listOf("教室では聞こえない", "two words")),
        ).forEach { case ->
            val units = planPageTranslationUnits(blocks, case.presentation)
            assertEquals(case.presentation.name, case.expected, units.map(PageTranslationUnit::sourceText))
            assertEquals(case.presentation.name, listOf(0, 1), units.map(PageTranslationUnit::blockIndex))
            assertEquals(case.presentation.name, listOf(10, 90), units.map { it.geometry.left })
            assertEquals(case.presentation.name, listOf(20, 20), units.map { it.geometry.top })
            assertEquals(case.presentation.name, listOf(60, 140), units.map { it.geometry.right })
            assertEquals(case.presentation.name, listOf(80, 80), units.map { it.geometry.bottom })
        }
    }

    @Test
    fun requestPreparationKeepsOriginalSourceBoxesAndBlockMembershipForNativeRendering() {
        val firstSource = "Bright rivers run through quiet\nvalleys."
        val secondSource = "The small orange fox reads a\nuseful book."
        val firstBoxes = listOf(block("", 10).boundingBox, block("", 15).boundingBox)
        val first = block(firstSource, 10).copy(sourceBoxes = firstBoxes)
        val second = block(secondSource, 90)
        val blocks = listOf(first, second)
        for (presentation in RenderMode.entries) {
            val units = planPageTranslationUnits(blocks, presentation)
            assertEquals(listOf("Bright rivers run through quiet valleys.", "The small orange fox reads a useful book."), units.map { it.sourceText })
            assertEquals(listOf(listOf(0), listOf(1)), units.map { it.blockIndexes })
            assertEquals(listOf(firstSource, secondSource), blocks.map { it.text })
            assertSame(first, blocks[0]); assertSame(second, blocks[1])
            assertSame(firstBoxes, blocks[0].sourceBoxes)
            assertEquals(listOf(10, 90), blocks.map { it.boundingBox.left })
            assertEquals(listOf(60, 140), blocks.map { it.boundingBox.right })
        }
    }

    @Test
    fun history_tableDriven_blocksStayIdenticalAndFloatingBecomesSingleLine() {
        val frame = DialogueContextFrame(
            listOf(
                DialogueContextItem(
                    id = 1,
                    source = "原\n文",
                    translation = "译\n文",
                    reusableOutput = "cached\nvalue",
                    geometry = DialogueGeometry(1, 2, 3, 4),
                )
            )
        )

        assertSame(
            "Blocks history must remain the original object",
            frame,
            PageTranslationPresentationTextPolicy.normalizeHistory(RenderMode.BLOCKS, frame),
        )
        val floating = PageTranslationPresentationTextPolicy.normalizeHistory(
            RenderMode.FLOATING_WINDOW,
            frame,
        )!!.items.single()
        assertEquals("原文", floating.source)
        assertEquals("译文", floating.translation)
        assertEquals("cached value", floating.reusableOutput)
        assertEquals(frame.items.single().geometry, floating.geometry)
    }

    private fun block(text: String, left: Int): TextBlock {
        val bounds = Rect().apply {
            this.left = left
            top = 20
            right = left + 50
            bottom = 80
        }
        return TextBlock(text = text, boundingBox = bounds)
    }
}
