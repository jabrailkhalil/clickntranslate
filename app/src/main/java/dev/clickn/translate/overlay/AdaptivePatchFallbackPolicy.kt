// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.overlay

/** Resolves translated blocks that still need their adaptive erase background after patch display. */
internal object AdaptivePatchFallbackPolicy {
    fun unresolvedBlockIndices(
        translatedBlockIndices: Set<Int>,
        displayedPatchBlockIndices: Set<Int>,
    ): Set<Int> = translatedBlockIndices
        .asSequence()
        .filter { it >= 0 && it !in displayedPatchBlockIndices }
        .toCollection(linkedSetOf())
}
