package dev.clickn.translate.data

import java.util.Locale

internal val specializedTranslationEngines = setOf(
    TranslatorEngine.VOLC, TranslatorEngine.BAIDU_FANYI, TranslatorEngine.TENCENT,
    TranslatorEngine.NIUTRANS, TranslatorEngine.YOUDAO_PICTRANS, TranslatorEngine.LOCAL_SAKURA,
)

/** Language preferences indicate relevance; no location or country permission is needed. */
internal fun chineseToolsRelevant(targetLang: String, locale: Locale): Boolean =
    targetLang.substringBefore('-').equals("zh", ignoreCase = true) || locale.language == "zh"

internal fun visibleTranslationPresets(
    presets: List<TranslationPreset>, targetLang: String, activeId: String, locale: Locale,
): List<TranslationPreset> = presets.filter {
    it.id != TranslationPresetCatalog.BUILTIN_MANGA_JA_ZH || it.id == activeId ||
        chineseToolsRelevant(targetLang, locale)
}
