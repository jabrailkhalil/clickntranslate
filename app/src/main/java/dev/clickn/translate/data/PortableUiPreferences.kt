package dev.clickn.translate.data

import dev.clickn.translate.ui.theme.ThemeAccent
import dev.clickn.translate.ui.theme.ThemeMode
import kotlinx.serialization.Serializable

/** Only portable appearance choices; window geometry, custom images and permissions stay local. */
@Serializable
data class PortableUiPreferences(
    val themeMode: Int? = null,
    val accent: String? = null,
    val languageTag: String? = null,
    val companion: String? = null,
) {
    internal fun validate() {
        require(themeMode == null || themeMode in ThemeMode.FOLLOW_SYSTEM..ThemeMode.PAPER_NORD) {
            "Unsupported interface theme."
        }
        require(accent == null || ThemeAccent.entries.any { it.name == accent }) {
            "Unsupported interface accent."
        }
        require(languageTag == null || languageTag in LANGUAGE_TAGS) { "Unsupported interface language." }
        require(companion == null || companion in COMPANIONS) { "Unsupported portable companion." }
    }

    companion object {
        internal val LANGUAGE_TAGS = setOf("", "en", "ru", "de", "fr", "es", "zh-CN")
        internal val COMPANIONS = setOf("chester", "doc", "pancake", "bubu", "momo", "action", "logo")
    }
}
