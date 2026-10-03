// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.overlay

internal object OcrDebugBoxLabelFormatter {
    fun format(
        source: String,
        translation: String,
        showSource: Boolean,
        showTranslation: Boolean,
        sourceLabel: String,
        translationLabel: String,
    ): String = buildList {
        if (showSource) add("$sourceLabel: ${source.trim()}")
        if (showTranslation) add("$translationLabel: ${translation.trim()}")
    }.joinToString("\n")
}
