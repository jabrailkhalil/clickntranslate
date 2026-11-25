package dev.clickn.translate.ocr

import android.graphics.Rect
import kotlin.math.abs

internal data class PaddleArabicTextLine(val text: String, val bounds: MergeDebugRect)
private data class ArabicColumnGap(val row: Int, val left: Int, val right: Int, val top: Int)

/** Reassemble adjacent parts of a line in reading order; a recurring gutter separates columns. */
internal fun groupPaddleArabicTextRows(lines: List<PaddleArabicTextLine>): List<List<Int>> {
    val rows = groupHorizontalLineRects(lines.map { it.bounds }, List(lines.size) { null },
        alignmentTolerance = 0.25f, adjacentGapRatio = 0.5f, heightRatioLimit = 1.5f)
    val gaps = if (rows.size < 2) emptyList() else rows.flatMapIndexed { index, row ->
        row.zipWithNext().mapNotNull { (a, b) ->
            val left = lines[a].bounds
            val right = lines[b].bounds
            if (left.right < right.left) ArabicColumnGap(index, left.right, right.left, left.top) else null
        }
    }
    return rows.flatMapIndexed { index, row ->
        val hasArabic = row.any { TesseractTextPolicy.language(lines[it].text) == "ar" }
        val hasLatin = row.any { TesseractTextPolicy.language(lines[it].text) == "en" }
        if (row.size > 1 && hasArabic && !hasLatin && row.all { TesseractTextPolicy.rtl(lines[it].text) }) {
            val groups = mutableListOf(mutableListOf(row.first()))
            for ((leftId, rightId) in row.zipWithNext()) {
                val left = lines[leftId].bounds
                val right = lines[rightId].bounds
                // A narrow two-column table can have a gap as small as an ordinary word space.
                val gutter = right.left > left.right && gaps.any { other ->
                    other.row != index && abs(other.top - left.top) in 1..(3 * left.height) &&
                        minOf(right.left, other.right) > maxOf(left.right, other.left)
                }
                if (gutter) groups.add(mutableListOf())
                groups.last().add(rightId)
            }
            groups.asReversed().map { it.asReversed() }
        } else if (row.size > 1 && hasArabic && hasLatin) {
            // The row runs right to left, while a product name such as "Android Studio"
            // can be split into several OCR boxes that still read left to right.
            val logical = row.sortedByDescending { lines[it].bounds.right }.toMutableList()
            var runStart = 0
            for (i in 0..logical.size) {
                if (i == logical.size || !isLtrFragment(lines[logical[i]].text)) {
                    if (i - runStart > 1) logical.subList(runStart, i).reverse()
                    runStart = i + 1
                }
            }
            listOf(logical)
        } else row.map { listOf(it) }
    }.sortedWith(compareBy({ row -> row.minOf { lines[it].bounds.top } },
        { row -> -row.maxOf { lines[it].bounds.right } }))
}

private fun isLtrFragment(text: String): Boolean =
    TesseractTextPolicy.language(text) == "en" || (text.any(Char::isDigit) && text.none(Char::isLetter))

/** Reuse the common immutable-box paragraph geometry, with Arabic column/alignment boundaries. */
internal fun groupPaddleArabicParagraphRows(lines: List<PaddleArabicTextLine>): List<List<Int>> {
    val boundaries = lines.mapIndexed { index, line ->
        if (TesseractTextPolicy.language(line.text) == "ar" && TesseractTextPolicy.rtl(line.text)) 0 else index + 1
    }
    return groupHorizontalParagraphRects(lines.map { it.bounds }, boundaries,
        verticalGapRatio = 1f, horizontalOverlapRatio = 0.5f).flatMap { group ->
        val paragraphs = mutableListOf<MutableList<Int>>()
        group.forEach { index ->
            val previous = paragraphs.lastOrNull()?.lastOrNull()
            val a = previous?.let { lines[it].bounds }
            val b = lines[index].bounds
            val height = a?.let { minOf(it.height, b.height).toFloat() }
            val sameColumn = a != null && height != null &&
                maxOf(a.height, b.height) <= height * 1.6f && abs(a.right - b.right) <= height * 0.9f
            if (sameColumn) paragraphs.last().add(index) else paragraphs.add(mutableListOf(index))
        }
        paragraphs
    }
}

/** The Arabic pack always supplies coherent MT units, independently of the optional UI merge mode. */
internal fun preparePaddleArabicParagraphs(blocks: List<TextBlock>): List<TextBlock> {
    fun List<TextBlock>.lines() = map { block ->
        val b = block.boundingBox
        PaddleArabicTextLine(block.text, MergeDebugRect(b.left, b.top, b.right, b.bottom))
    }
    val rows = groupPaddleArabicTextRows(blocks.lines()).map { indexes ->
        mergeArabicMembers(indexes.map(blocks::get), " ")
    }
    return groupPaddleArabicParagraphRows(rows.lines()).mapIndexed { paragraphId, indexes ->
        val members = indexes.map(rows::get)
        val paragraph = mergeArabicMembers(members, "\n")
        if (TesseractTextPolicy.language(paragraph.text) == "ar") paragraph.copy(
            regionId = paragraphId,
            parentRegionId = paragraphId,
            regionGranularity = TextRegionGranularity.PARAGRAPH,
        ) else paragraph
    }
}

private fun mergeArabicMembers(members: List<TextBlock>, separator: String): TextBlock {
    if (members.size == 1) return members.single()
    val sources = members.flatMap { it.sourceBoxesOrBoundingBox() }
    val text = members.joinToString(separator) { it.text }
    val weight = members.sumOf { it.text.count(Char::isLetter).coerceAtLeast(1) }
    return members.first().copy(
        text = text,
        boundingBox = Rect(sources.minOf { it.left }, sources.minOf { it.top },
            sources.maxOf { it.right }, sources.maxOf { it.bottom }),
        sourceBoxes = sources,
        confidence = (members.sumOf { (it.confidence * it.text.count(Char::isLetter).coerceAtLeast(1)).toDouble() } / weight).toFloat(),
        recognizedLanguage = TesseractTextPolicy.language(text),
        layoutOrientation = if (TesseractTextPolicy.rtl(text)) TextOrientation.HORIZONTAL_RTL else TextOrientation.HORIZONTAL_LTR,
    )
}
