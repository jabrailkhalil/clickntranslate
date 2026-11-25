package dev.clickn.translate.ocr

/** A paragraph-to-lines refinement must be accepted or rejected as one overlap component. */
internal fun <T> completeAutoOcrRefinements(
    original: List<T>,
    refined: List<T>,
    language: String,
    evidenceOf: (T) -> AutoOcrEvidence,
    overlaps: (T, T) -> Boolean,
    covers: (T, List<T>) -> Boolean,
): List<T> {
    val candidates = refined.filter { evidenceOf(it).language == language }
    val oldByNew = Array(candidates.size) { mutableListOf<Int>() }
    val newByOld = Array(original.size) { mutableListOf<Int>() }
    candidates.forEachIndexed { newIndex, candidate ->
        original.forEachIndexed { oldIndex, old ->
            if (overlaps(candidate, old)) {
                oldByNew[newIndex] += oldIndex
                newByOld[oldIndex] += newIndex
            }
        }
    }
    val visited = BooleanArray(candidates.size)
    val accepted = BooleanArray(candidates.size)
    candidates.indices.forEach { start ->
        if (visited[start]) return@forEach
        val pending = ArrayDeque<Int>()
        val newMembers = mutableListOf<Int>()
        val oldMembers = linkedSetOf<Int>()
        pending += start
        visited[start] = true
        while (pending.isNotEmpty()) {
            val index = pending.removeFirst()
            newMembers += index
            oldByNew[index].forEach { oldIndex ->
                if (oldMembers.add(oldIndex)) newByOld[oldIndex].forEach { other ->
                    if (!visited[other]) { visited[other] = true; pending += other }
                }
            }
        }
        val oldRegions = oldMembers.map(original::get)
        val newRegions = newMembers.map(candidates::get)
        val before = oldRegions.map(evidenceOf)
        val after = newRegions.map(evidenceOf)
        if (before.any { it.language != null && it.language != language }) return@forEach
        val previousLetters = before.sumOf { it.text.count(Char::isLetter).toLong() }
        val nextLetters = after.sumOf { it.text.count(Char::isLetter).toLong() }
        // A missing short final line is not a successful refinement of a complete paragraph.
        if (nextLetters * 10 < previousLetters * 9) return@forEach
        val combined = AutoOcrEvidence(after.joinToString("\n") { it.text }, language,
            after.map { it.confidence }.filter(Float::isFinite).average().takeIf(Double::isFinite)?.toFloat() ?: 0f)
        if (AutoOcrLanguagePolicy.canRefine(before, combined, language) &&
            oldRegions.all { covers(it, newRegions) }) {
            newMembers.forEach { accepted[it] = true }
        }
    }
    return candidates.filterIndexed { index, _ -> accepted[index] }
}

/** Measure union coverage per original line, without retaining bitmap pixels or counting overlaps twice. */
internal fun coversAutoOcrSourceRects(original: List<MergeDebugRect>, refined: List<MergeDebugRect>): Boolean =
    original.isNotEmpty() && original.all { source ->
        val area = source.width.toLong() * source.height
        if (area <= 0) return@all false
        val clipped = refined.mapNotNull { box ->
            val left = maxOf(source.left, box.left)
            val right = minOf(source.right, box.right)
            val top = maxOf(source.top, box.top)
            val bottom = minOf(source.bottom, box.bottom)
            if (right > left && bottom > top) MergeDebugRect(left, top, right, bottom) else null
        }
        if (clipped.any { it.width.toLong() * it.height * 2 >= area }) return@all true
        val edges = clipped.flatMap { listOf(it.left, it.right) }.distinct().sorted()
        var covered = 0L
        edges.zipWithNext().forEach { (left, right) ->
            val intervals = clipped.filter { it.left <= left && it.right >= right }.sortedBy { it.top }
            var bottom = Int.MIN_VALUE
            var height = 0L
            intervals.forEach { box ->
                height += (box.bottom.toLong() - maxOf(box.top, bottom)).coerceAtLeast(0)
                bottom = maxOf(bottom, box.bottom)
            }
            covered += (right.toLong() - left) * height
        }
        covered * 2 >= area
    }
