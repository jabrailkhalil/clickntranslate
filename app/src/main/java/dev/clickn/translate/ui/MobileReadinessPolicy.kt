package dev.clickn.translate.ui

import dev.clickn.translate.data.*
import dev.clickn.translate.translate.MlKitLanguagePolicy

internal val offlineTranslationEngines = setOf(TranslatorEngine.GOOGLE_ML_KIT, TranslatorEngine.LOCAL_HY_MT2, TranslatorEngine.LOCAL_SAKURA)
internal fun translationNeedsConfiguration(s: Settings): Boolean = when (s.translatorEngine) {
    TranslatorEngine.OPENAI -> s.apiKey.isBlank() || s.model.isBlank() || s.baseUrl.isBlank()
    TranslatorEngine.ANTHROPIC -> s.anthropicApiKey.isBlank() || s.anthropicModel.isBlank() || s.anthropicBaseUrl.isBlank()
    TranslatorEngine.DEEPL -> if (s.deeplProtocol == DeeplProtocol.OFFICIAL) s.deeplApiKey.isBlank() else s.deeplBaseUrl.isBlank()
    TranslatorEngine.NIUTRANS -> s.niuTransApiKey.isBlank() || (s.niuTransMode == NiuTransMode.FLASH && s.niuTransAppId.isBlank())
    TranslatorEngine.YOUDAO_PICTRANS -> s.youdaoAppKey.isBlank() || s.youdaoAppSecret.isBlank()
    TranslatorEngine.VOLC -> s.volcAccessKeyId.isBlank() || s.volcSecretAccessKey.isBlank()
    TranslatorEngine.BAIDU_FANYI -> s.baiduFanyiAppId.isBlank() || s.baiduFanyiSecretKey.isBlank()
    TranslatorEngine.TENCENT -> s.tencentSecretId.isBlank() || s.tencentSecretKey.isBlank()
    TranslatorEngine.LINGVA -> s.lingvaBaseUrl.isBlank()
    TranslatorEngine.LIBRETRANSLATE -> s.libreTranslateBaseUrl.isBlank()
    else -> false
}
internal fun mobileLanguagePair(s: Settings, source: Boolean, code: String): Settings {
    val other = if (source) s.targetLang else s.sourceLang
    val conflict = if (s.translatorEngine == TranslatorEngine.GOOGLE_ML_KIT)
        runCatching { MlKitLanguagePolicy.resolveTarget(code) == MlKitLanguagePolicy.resolveTarget(other) }.getOrDefault(false)
    else translationLanguageCodesConflict(code, other)
    if (code != "auto" && other != "auto" && conflict) return s.copy(sourceLang = s.targetLang,
        targetLang = s.sourceLang.takeUnless { it == "auto" } ?: if (code == "en") "ru" else "en")
    return if (source) s.copy(sourceLang = code) else s.copy(targetLang = code)
}
internal fun mobileMlKitPair(s: Settings): Settings {
    val target = runCatching { MlKitLanguagePolicy.resolveTarget(s.targetLang) }.getOrNull() ?: "en"
    val source = runCatching { MlKitLanguagePolicy.resolveConfiguredSource(s.sourceLang) }.getOrNull()
        .takeUnless { it == target } ?: if (target == "en") "ru" else "en"
    return s.copy(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT, sourceLang = source, targetLang = target)
}
