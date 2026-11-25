package dev.clickn.translate.ocr

import android.graphics.Rect
import kotlin.math.abs

internal data class MlKitParagraphLine(
    val text: String,
    val bounds: MergeDebugRect,
    val parent: Int?,
    val orientation: TextOrientation?,
    val granularity: TextRegionGranularity,
    val language: String?,
)

/** Native parents are semantic evidence; crossing parents requires a much narrower EN wrap. */
internal fun groupMlKitParagraphLines(
    lines: List<MlKitParagraphLine>,
    englishOnly: Boolean = false,
): List<List<Int>> {
    fun eligible(line: MlKitParagraphLine): Boolean = line.parent != null &&
        line.granularity == TextRegionGranularity.LINE && line.bounds.width > 0 && line.bounds.height > 0 &&
        (line.orientation == TextOrientation.HORIZONTAL_LTR || line.orientation == TextOrientation.HORIZONTAL_RTL) &&
        (!englishOnly || isAutomaticEnglishParagraphLine(line))

    val nativeGroups = mutableListOf<List<Int>>()
    val consumed = BooleanArray(lines.size)
    lines.indices.forEach { index ->
        if (consumed[index]) return@forEach
        val line = lines[index]
        if (!eligible(line)) {
            nativeGroups += listOf(index)
            consumed[index] = true
        } else {
            val siblings = lines.indices.filter {
                eligible(lines[it]) && lines[it].parent == line.parent && lines[it].orientation == line.orientation
            }
            groupHorizontalParagraphRects(siblings.map { lines[it].bounds }, List(siblings.size) { null },
                verticalGapRatio = 0.8f, horizontalOverlapRatio = 0.3f).forEach { group ->
                val members = group.map(siblings::get)
                if (englishOnly && members.none { lines[it].language == "en" }) {
                    // An entirely unidentified/foreign Latin region cannot acquire an
                    // English paragraph merely by sharing a detector parent.
                    members.forEach { nativeGroups += listOf(it) }
                } else nativeGroups += members
                members.forEach { consumed[it] = true }
            }
        }
    }
    fun continues(previous: List<Int>, next: List<Int>): Boolean {
        // Never search past another detector block, including an interleaved side column.
        if (previous.max() + 1 != next.min()) return false
        val before = lines[previous.last()]
        val after = lines[next.first()]
        if (!eligible(before) || !eligible(after) || before.parent == after.parent) return false
        if (before.orientation != TextOrientation.HORIZONTAL_LTR || after.orientation != before.orientation) return false
        if (before.language != "en") return false
        val unknownLatinTail = after.language == null || after.language == "und" || after.language == "latin"
        if (after.language != "en" && !unknownLatinTail) return false
        val a = before.text.trim()
        val b = after.text.trim()
        val nextCharacter = b.firstOrNull() ?: return false
        if (a.lastOrNull()?.isLetterOrDigit() != true || nextCharacter !in 'a'..'z') return false
        // A short OCR tail can lack enough language-ID evidence. Only a closed sentence
        // continuation may borrow the preceding English evidence; an unlabeled UI token
        // without terminal punctuation must remain independent.
        if (unknownLatinTail && b.last() !in ENGLISH_SENTENCE_ENDINGS) return false
        if (a.count(Char::isLetter) < 18 || a.split(Regex("\\s+")).size < 4) return false
        if ((a + b).any { it.isLetter() && Character.UnicodeScript.of(it.code) != Character.UnicodeScript.LATIN }) return false
        val first = before.bounds
        val second = after.bounds
        val height = minOf(first.height, second.height).toFloat()
        // A short final word can have a smaller glyph box despite sharing the same
        // font: a long prefix can contain descenders absent from "leaves.".
        // Only a narrow, closed tail gets this allowance; ordinary wraps stay strict.
        val closedShortTail = b.length <= 32 && b.split(Regex("\\s+")).size <= 3 && b.none(Char::isUpperCase) &&
            b.last() in ENGLISH_SENTENCE_ENDINGS && second.width < first.width
        val maximumHeight = maxOf(first.height, second.height).toFloat()
        val heightRatio = if (closedShortTail) 1.5f else 1.25f
        if (maximumHeight > height * heightRatio || abs(first.left - second.left) > height * 0.35f) return false
        if (first.width < height * 5f || second.top < first.bottom - height * 0.1f) return false
        val columnWidth = lines.filter {
            eligible(it) && it.orientation == before.orientation &&
                maxOf(it.bounds.height, first.height) <= minOf(it.bounds.height, first.height) * 1.25f &&
                abs(it.bounds.left - first.left) <= height * 0.35f
        }.maxOfOrNull { it.bounds.width } ?: first.width
        if (first.width < columnWidth * 0.75f) return false
        val maximumGap = if (closedShortTail) maximumHeight * 0.5f else height * 0.45f
        if (second.top - first.bottom > maximumGap) return false
        if (groupHorizontalParagraphRects(listOf(first, second), listOf(null, null),
                verticalGapRatio = maximumGap / height,
                horizontalOverlapRatio = 0.8f) != listOf(listOf(0, 1))) return false
        val members = (previous + next).toSet()
        return lines.indices.none { index ->
            val box = lines[index].bounds
            index !in members && box.bottom > first.bottom && box.top < second.top &&
                box.right > minOf(first.left, second.left) && box.left < maxOf(first.right, second.right)
        }
    }
    val paragraphs = mutableListOf<List<Int>>()
    nativeGroups.sortedBy { it.min() }.forEach { group ->
        val previous = paragraphs.lastOrNull()
        if (previous != null && continues(previous, group)) paragraphs[paragraphs.lastIndex] = previous + group
        else paragraphs += group
    }
    return paragraphs
}

/** Keep every line's original erasure/position box while presenting one coherent MT paragraph. */
internal fun prepareMlKitParagraphBlocks(blocks: List<TextBlock>): List<TextBlock> =
    prepareMlKitParagraphBlocks(blocks, englishOnly = false)

/** Only this recognizer pass's tagged English lines may be repaired before Auto mixes passes. */
internal fun prepareAutomaticEnglishParagraphBlocks(blocks: List<TextBlock>): List<TextBlock> =
    prepareMlKitParagraphBlocks(blocks, englishOnly = true)

private fun prepareMlKitParagraphBlocks(blocks: List<TextBlock>, englishOnly: Boolean): List<TextBlock> =
    groupMlKitParagraphLines(blocks.map { block ->
        val box = block.boundingBox
        MlKitParagraphLine(block.text, MergeDebugRect(box.left, box.top, box.right, box.bottom),
            block.parentRegionId, block.layoutOrientation, block.regionGranularity, block.recognizedLanguage)
    }, englishOnly = englishOnly).map { indexes ->
        if (indexes.size == 1) blocks[indexes.single()]
        else {
            val members = indexes.map(blocks::get)
            val weight = members.sumOf { it.text.count(Char::isLetter).coerceAtLeast(1) }
            members.first().copy(
                text = members.joinToString("\n") { it.text },
                boundingBox = Rect(members.minOf { it.boundingBox.left }, members.minOf { it.boundingBox.top },
                    members.maxOf { it.boundingBox.right }, members.maxOf { it.boundingBox.bottom }),
                sourceBoxes = members.flatMap { it.sourceBoxesOrBoundingBox() },
                confidence = (members.sumOf { (it.confidence * it.text.count(Char::isLetter).coerceAtLeast(1)).toDouble() } / weight).toFloat(),
                recognizedLanguage = members.map { it.recognizedLanguage }.distinct().singleOrNull(),
                parentRegionId = members.map { it.parentRegionId }.distinct().singleOrNull(),
                regionGranularity = TextRegionGranularity.PARAGRAPH,
            )
        }
    }

private fun isAutomaticEnglishParagraphLine(line: MlKitParagraphLine): Boolean {
    if (line.orientation != TextOrientation.HORIZONTAL_LTR) return false
    val text = line.text.trim()
    if (text.none(Char::isLetter) || text.any {
            it.isLetter() && Character.UnicodeScript.of(it.code) != Character.UnicodeScript.LATIN
        }) return false
    if (line.language == "en") return true
    if (line.language != null && line.language != "und" && line.language != "latin") return false
    return text.first() in 'a'..'z' && text.last() in ENGLISH_SENTENCE_ENDINGS
}

private const val ENGLISH_SENTENCE_ENDINGS = ".!?\u2026"
