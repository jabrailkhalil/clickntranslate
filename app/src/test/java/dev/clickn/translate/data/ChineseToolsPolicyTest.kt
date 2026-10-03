package dev.clickn.translate.data

import java.util.Locale
import org.junit.Assert.*
import org.junit.Test

class ChineseToolsPolicyTest {
    @Test fun newSettingsFollowTheUsersLanguageAndScript() {
        val original = Locale.getDefault()
        try {
            listOf("ru-RU" to "ru", "en-US" to "en", "sv-SE" to "sv",
                "zh-CN" to "zh-CN", "zh-TW" to "zh-TW", "zh-Hant" to "zh-TW").forEach { (tag, target) ->
                Locale.setDefault(Locale.forLanguageTag(tag))
                assertEquals(target, Settings().targetLang)
                assertEquals(target, TranslationPreset("custom", "Custom").targetLang)
            }
        } finally { Locale.setDefault(original) }
    }
    @Test fun chineseProfileAppearsWhenRelevantOrAlreadySelected() {
        val preset = TranslationPresetCatalog.builtIns().single()
        val custom = TranslationPreset("my-profile", "My Japanese profile", targetLang = "ru")
        val all = listOf(preset, custom)
        assertEquals(listOf(custom), visibleTranslationPresets(all, "ru", "", Locale.forLanguageTag("ru")))
        assertEquals(all, visibleTranslationPresets(all, "zh-TW", "", Locale.ENGLISH))
        assertEquals(all, visibleTranslationPresets(all, "ru", "", Locale.CHINESE))
        assertEquals(all, visibleTranslationPresets(all, "ru", preset.id, Locale.ENGLISH))
    }
}
