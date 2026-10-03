// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import java.util.Locale

/** Human-readable name for language tags, including regional system voice tags. */
internal fun languageDisplayName(tag: String, displayLocale: Locale = Locale.getDefault()): String {
    val normalized = tag.trim().replace('_', '-')
    val locale = Locale.forLanguageTag(normalized)
    if (locale.language.isBlank()) return tag
    return locale.getDisplayName(displayLocale).takeIf { it.isNotBlank() } ?: tag
}
