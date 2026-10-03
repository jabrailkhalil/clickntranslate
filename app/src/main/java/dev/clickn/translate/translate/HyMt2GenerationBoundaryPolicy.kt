// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

/** Native generation boundary for one Hy-MT2 translation item with contextual background. */
internal object HyMt2GenerationBoundaryPolicy {
    private const val OUTPUT_LINE_ALLOWANCE = 1

    fun maxOutputLines(
        source: String,
        requestHadBackground: Boolean,
    ): Int {
        if (!requestHadBackground) return 0
        val sourceLines = source.lineSequence().count().coerceAtLeast(1)
        return sourceLines + OUTPUT_LINE_ALLOWANCE
    }
}
