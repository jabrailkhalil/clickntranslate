package dev.clickn.translate.ui

import dev.clickn.translate.data.*
import dev.clickn.translate.translate.MlKitLanguagePolicy
import dev.clickn.translate.capture.CaptureStartMode

internal enum class MobileReadinessKey {
    LANGUAGES, SERVICE, OCR, TRANSLATION_MODELS, OVERLAY, CAPTURE, HERO, NOTIFICATIONS, BATTERY, ACCESSIBILITY,
}

internal data class MobileReadinessItem(val key: MobileReadinessKey, val ready: Boolean?, val required: Boolean)

internal fun mobileReadinessItems(
    settings: Settings, models: MobileModelState, overlay: Boolean,
    captureMode: CaptureStartMode?, shizukuReady: Boolean?, heroSelected: Boolean,
    notifications: Boolean, battery: Boolean, accessibility: Boolean,
): List<MobileReadinessItem> = buildList {
    add(MobileReadinessItem(MobileReadinessKey.LANGUAGES, setupLanguagePairReady(settings), true))
    add(MobileReadinessItem(MobileReadinessKey.SERVICE, !translationNeedsConfiguration(settings), true))
    add(MobileReadinessItem(MobileReadinessKey.OCR, if (models.checking) null else models.ocrReady, true))
    if (settings.translatorEngine in offlineTranslationEngines) {
        add(MobileReadinessItem(MobileReadinessKey.TRANSLATION_MODELS, if (models.checking) null else models.translationReady, true))
    }
    add(MobileReadinessItem(MobileReadinessKey.OVERLAY, overlay, true))
    add(MobileReadinessItem(MobileReadinessKey.CAPTURE, when (captureMode) {
        null -> null
        CaptureStartMode.SYSTEM -> true
        CaptureStartMode.SHIZUKU -> shizukuReady
    }, true))
    add(MobileReadinessItem(MobileReadinessKey.HERO, heroSelected, false))
    add(MobileReadinessItem(MobileReadinessKey.NOTIFICATIONS, notifications, false))
    add(MobileReadinessItem(MobileReadinessKey.BATTERY, battery, false))
    add(MobileReadinessItem(MobileReadinessKey.ACCESSIBILITY, accessibility, false))
}

internal val offlineTranslationEngines = setOf(TranslatorEngine.GOOGLE_ML_KIT, TranslatorEngine.LOCAL_HY_MT2, TranslatorEngine.LOCAL_SAKURA)

/** Screen readiness has the same prerequisites as the start action; optional grants do not block it. */
internal fun mobileScreenReady(settings: Settings, models: MobileModelState, overlay: Boolean,
    captureMode: CaptureStartMode? = CaptureStartMode.SYSTEM, shizukuReady: Boolean? = null): Boolean =
    overlay && !models.checking && models.ocrReady == true && setupLanguagePairReady(settings) &&
        !translationNeedsConfiguration(settings) &&
        (settings.translatorEngine !in offlineTranslationEngines || models.translationReady == true) &&
        captureMode != null && (captureMode != CaptureStartMode.SHIZUKU || shizukuReady == true)

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
