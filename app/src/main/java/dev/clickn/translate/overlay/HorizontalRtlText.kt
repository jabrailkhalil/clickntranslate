// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.overlay

/**
 * The OCR box's direction describes its source, not the translated characters. Keep translations
 * in logical order and let the layout's first-strong heuristic resolve each target paragraph.
 * In particular, an RTL override would reverse Cyrillic/Latin runs and even Latin words in Arabic.
 * Also used by the gallery's StaticLayout, whose default direction is first-strong.
 */
internal fun horizontalRtlDisplayText(text: String): String = text
