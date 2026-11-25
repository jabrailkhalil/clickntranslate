package dev.clickn.translate.ocr

import dev.clickn.translate.translate.OcrTranslationRequestTextPolicy
import org.junit.Assert.assertEquals
import org.junit.Test

class MlKitParagraphGroupingTest {
    @Test fun recordedNativeSplitAndWrappedParentBecomeTwoWholeSentencesWithoutJoiningAColumn() {
        // Actual MLKit geometry/parents: .tmp/c35-ocr-baseline/geometry-5584.json.
        // First sentence is split across native blocks 2/3; second is two lines of block 4.
        val lines = listOf(
            line("Touches: 0", MergeDebugRect(48, 962, 321, 1006), 0),
            line("UID: 10217", MergeDebugRect(51, 1037, 227, 1064), 1),
            line("Bright rivers run through quiet", MergeDebugRect(53, 1095, 877, 1155), 2),
            line("valleys.", MergeDebugRect(49, 1168, 249, 1228), 3),
            line("The small orange fox reads a", MergeDebugRect(64, 1312, 855, 1371), 4),
            line("useful book.", MergeDebugRect(51, 1383, 386, 1437), 4),
            // Constructed independent right column at the same height as the first paragraph.
            line("Another column", MergeDebugRect(950, 1095, 1075, 1155), 5),
        )
        val groups = groupMlKitParagraphLines(lines)
        assertEquals(listOf(listOf(0), listOf(1), listOf(2, 3), listOf(4, 5), listOf(6)), groups)
        val requests = groups.map { group ->
            OcrTranslationRequestTextPolicy.normalize(group.joinToString("\n") { lines[it].text })
        }
        assertEquals(listOf("Touches: 0", "UID: 10217", "Bright rivers run through quiet valleys.",
            "The small orange fox reads a useful book.", "Another column"), requests)
        assertEquals("valleys.", lines[3].text)
        assertEquals(MergeDebugRect(49, 1168, 249, 1228), lines[3].bounds)
    }

    @Test fun continuationRejectsLabelsSentenceEndsColumnsVerticalTextAndForeignBlocks() {
        val first = line("Bright rivers run through quiet", MergeDebugRect(10, 100, 610, 140), 1)
        val next = line("valleys.", MergeDebugRect(12, 150, 180, 190), 2)
        val rejected = listOf(
            "short label" to listOf(first.copy(text = "Profile"), next),
            "completed sentence" to listOf(first.copy(text = first.text + "."), next),
            "label punctuation" to listOf(first.copy(text = first.text + ":"), next),
            "new capitalized sentence" to listOf(first, next.copy(text = "Valleys.")),
            "paragraph gap" to listOf(first, next.copy(bounds = MergeDebugRect(12, 190, 180, 230))),
            "another column" to listOf(first, next.copy(bounds = MergeDebugRect(650, 150, 850, 190))),
            "different font size" to listOf(first, next.copy(bounds = MergeDebugRect(12, 150, 180, 220))),
            "vertical Japanese" to listOf(first.copy(orientation = TextOrientation.VERTICAL_RTL), next),
            "unconfirmed parent" to listOf(first.copy(parent = null), next),
            "native semantic region" to listOf(first.copy(granularity = TextRegionGranularity.PARAGRAPH), next),
            "different language" to listOf(first.copy(language = "fr"), next),
            "not a full line" to listOf(first, next,
                line("Independent long line below", MergeDebugRect(10, 300, 910, 340), 3)),
            "interleaved side column" to listOf(first,
                line("Other column", MergeDebugRect(700, 110, 950, 150), 3), next),
            "intervening physical block" to listOf(first, next,
                line("Other content", MergeDebugRect(20, 141, 220, 149), 3)),
        )
        rejected.forEach { (name, lines) ->
            assertEquals(name, lines.indices.map { listOf(it) }, groupMlKitParagraphLines(lines))
        }
        val nativeColumns = listOf(first, next.copy(parent = 1),
            line("Right column upper", MergeDebugRect(700, 100, 1100, 140), 1),
            line("right continuation", MergeDebugRect(702, 150, 1050, 190), 1))
        assertEquals("Even one detector parent must not join separate columns",
            listOf(listOf(0, 1), listOf(2, 3)), groupMlKitParagraphLines(nativeColumns))
    }

    @Test fun englishOrphanTailBecomesOneMtSentenceAfterPerPassLanguageTagging() {
        // Actual Debug OCR geometry: soak190/final-checks/25-debug-ocr-log.txt.
        // The final tail's raw height is 46, not the overlay's padded height of 57.
        // Parent IDs model the distinct native blocks before Auto clears their IDs.
        val independent = line("Silver trains travel beyond the mountain.",
            MergeDebugRect(65, 879, 945, 1017), 0).copy(granularity = TextRegionGranularity.PARAGRAPH)
        val prefix = line("Gentle winds carry the autumn", MergeDebugRect(67, 1382, 977, 1443), 1)
        val tail = line("leaves.", MergeDebugRect(67, 1467, 254, 1513), 2)
        for (tailLanguage in listOf("en", null, "und", "latin")) {
            val lines = listOf(independent, prefix, tail.copy(language = tailLanguage))
            val groups = groupMlKitParagraphLines(lines, englishOnly = true)
            assertEquals("tail language=$tailLanguage", listOf(listOf(0), listOf(1, 2)), groups)
            val requests = groups.map { group ->
                OcrTranslationRequestTextPolicy.normalize(group.joinToString("\n") { lines[it].text })
            }
            assertEquals(listOf("Silver trains travel beyond the mountain.",
                "Gentle winds carry the autumn leaves."), requests)
        }
    }

    @Test fun unknownTailCannotCrossLabelsSemanticRegionsColumnsOrForeignText() {
        val prefix = line("Gentle winds carry the autumn", MergeDebugRect(67, 1382, 977, 1443), 1)
        val tail = line("leaves.", MergeDebugRect(67, 1467, 254, 1524), 2).copy(language = null)
        val rejected = listOf(
            "short label" to listOf(prefix.copy(text = "Profile"), tail),
            "label delimiter" to listOf(prefix.copy(text = prefix.text + ":"), tail),
            "already complete sentence" to listOf(prefix.copy(text = prefix.text + "."), tail),
            "new capitalized label" to listOf(prefix, tail.copy(text = "Leaves.")),
            "unknown token without sentence closure" to listOf(prefix, tail.copy(text = "leaves")),
            "different known language" to listOf(prefix, tail.copy(language = "fr")),
            "Arabic language" to listOf(prefix, tail.copy(language = "ar")),
            "mixed Arabic script" to listOf(prefix, tail.copy(text = "leaves العربية.")),
            "RTL line" to listOf(prefix, tail.copy(orientation = TextOrientation.HORIZONTAL_RTL)),
            "no native parent" to listOf(prefix, tail.copy(parent = null)),
            "protected paragraph" to listOf(prefix, tail.copy(granularity = TextRegionGranularity.PARAGRAPH)),
            "separate paragraph gap" to listOf(prefix, tail.copy(bounds = MergeDebugRect(67, 1758, 254, 1815))),
            "outside short-tail gap limit" to listOf(prefix, tail.copy(bounds = MergeDebugRect(67, 1474, 254, 1531))),
            "different font size" to listOf(prefix, tail.copy(bounds = MergeDebugRect(67, 1467, 254, 1562))),
            "right column" to listOf(prefix, tail.copy(bounds = MergeDebugRect(1010, 1467, 1197, 1524))),
            "interleaved column" to listOf(prefix,
                line("Another column", MergeDebugRect(1010, 1382, 1270, 1443), 3), tail),
        )
        rejected.forEach { (name, lines) ->
            assertEquals(name, lines.indices.map { listOf(it) }, groupMlKitParagraphLines(lines))
            assertEquals("Auto English: $name", lines.indices.map { listOf(it) },
                groupMlKitParagraphLines(lines, englishOnly = true))
        }
    }

    @Test fun closedShortTailAllowanceRejectsUnrelatedTextAndPreservesOrdinaryWrapLimits() {
        val prefix = line("Gentle winds carry the autumn", MergeDebugRect(67, 1382, 977, 1443), 1)
        val tail = line("leaves.", MergeDebugRect(67, 1467, 254, 1513), 2)
        val rejected = listOf(
            "gap exceeds half the taller glyph box" to listOf(prefix,
                tail.copy(bounds = MergeDebugRect(67, 1474, 254, 1520))),
            "glyph-height ratio exceeds 1.5" to listOf(prefix,
                tail.copy(bounds = MergeDebugRect(67, 1467, 254, 1507))),
            "foreign continuation" to listOf(prefix, tail.copy(language = "fr")),
            "foreign prefix" to listOf(prefix.copy(language = "fr"), tail),
            "right column" to listOf(prefix,
                tail.copy(bounds = MergeDebugRect(1010, 1467, 1197, 1513))),
            "closed previous sentence" to listOf(prefix.copy(text = prefix.text + "."), tail),
            "four-word continuation" to listOf(prefix, tail.copy(text = "leaves in the valley.")),
            "uppercase word is not a lowercase tail" to listOf(prefix, tail.copy(text = "leaves HERE.")),
            "tail exceeds 32 characters" to listOf(prefix,
                tail.copy(text = "extraordinarily elongated continuations.")),
            "nonterminal short tail keeps strict glyph-height limit" to listOf(prefix,
                tail.copy(text = "leaves")),
            "long nonterminal continuation" to listOf(prefix,
                tail.copy(text = "leaves that fall in the forest")),
            "tail is not narrower than prefix" to listOf(prefix,
                tail.copy(bounds = MergeDebugRect(67, 1467, 977, 1513))),
            "mixed Arabic script" to listOf(prefix, tail.copy(text = "leaves العربية.")),
            "line alignment guard" to listOf(prefix,
                tail.copy(bounds = MergeDebugRect(84, 1467, 271, 1513))),
            "ordinary nonterminal gap stays at 0.45 of shorter height" to listOf(prefix,
                tail.copy(text = "leaves", bounds = MergeDebugRect(67, 1471, 254, 1532))),
        )
        rejected.forEach { (name, lines) ->
            for (englishOnly in listOf(false, true)) {
                assertEquals("$name (English only=$englishOnly)", listOf(listOf(0), listOf(1)),
                    groupMlKitParagraphLines(lines, englishOnly))
            }
        }
        assertEquals("Ordinary English wrapping still works within the strict bounds",
            listOf(listOf(0, 1)), groupMlKitParagraphLines(listOf(prefix,
                tail.copy(text = "leaves", bounds = MergeDebugRect(67, 1463, 254, 1524)))))
    }

    @Test fun automaticEnglishPreparationPreservesCjkRtlUnknownLanguagesAndProtectedRegions() {
        val first = line("Gentle winds carry the autumn", MergeDebugRect(67, 1382, 977, 1443), 1)
        val second = line("leaves.", MergeDebugRect(67, 1467, 254, 1524), 1)
        val untouched = listOf(
            "Japanese horizontal" to listOf(first.copy(text = "これは日本語です", language = "ja"),
                second.copy(text = "続きです。", language = "ja")),
            "Arabic RTL" to listOf(first.copy(text = "هذه فقرة عربية", language = "ar", orientation = TextOrientation.HORIZONTAL_RTL),
                second.copy(text = "للقراءة.", language = "ar", orientation = TextOrientation.HORIZONTAL_RTL)),
            "known French" to listOf(first.copy(text = "bonjour.", language = "fr"), second.copy(text = "monde.", language = "fr")),
            "unidentified Latin only" to listOf(first.copy(text = "bonjour.", language = null), second.copy(text = "monde.", language = null)),
            "mixed Arabic despite English tag" to listOf(first.copy(text = "English العربية"), second),
            "protected semantic paragraph" to listOf(first.copy(granularity = TextRegionGranularity.PARAGRAPH), second),
        )
        untouched.forEach { (name, lines) ->
            assertEquals(name, lines.indices.map { listOf(it) },
                groupMlKitParagraphLines(lines, englishOnly = true))
        }
        assertEquals("Confirmed English native siblings remain one paragraph",
            listOf(listOf(0, 1)), groupMlKitParagraphLines(listOf(first, second), englishOnly = true))
    }

    private fun line(text: String, bounds: MergeDebugRect, parent: Int) = MlKitParagraphLine(
        text, bounds, parent, TextOrientation.HORIZONTAL_LTR, TextRegionGranularity.LINE, "en",
    )
}
