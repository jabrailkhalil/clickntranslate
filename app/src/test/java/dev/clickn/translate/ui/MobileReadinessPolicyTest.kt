package dev.clickn.translate.ui

import dev.clickn.translate.data.*
import org.junit.Assert.*
import org.junit.Test

class MobileReadinessPolicyTest {
    @Test fun selectedShizukuLosingItsConnectionRemovesOnlyItsReadinessAndSystemRemainsAvailable() {
        val settings = Settings(translatorEngine = TranslatorEngine.GOOGLE, sourceLang = "auto", targetLang = "ru")
        val models = MobileModelState(checking = false, ocrReady = true)
        fun entries(ready: Boolean?) = mobileReadinessItems(settings, models, true,
            dev.clickn.translate.capture.CaptureStartMode.SHIZUKU, ready, false, false, false, false)
        val live = entries(true)
        val stopped = entries(false)
        assertTrue(live.filter { it.required }.all { it.ready == true })
        assertTrue(live.filterNot { it.required }.all { it.ready == false })
        assertEquals(listOf(MobileReadinessKey.CAPTURE), stopped.filter { it.required && it.ready != true }.map { it.key })
        assertEquals(live.filter { it.key != MobileReadinessKey.CAPTURE }, stopped.filter { it.key != MobileReadinessKey.CAPTURE })
        assertFalse(mobileScreenReady(settings, models, true, dev.clickn.translate.capture.CaptureStartMode.SHIZUKU, false))
        assertTrue(mobileScreenReady(settings, models, true, dev.clickn.translate.capture.CaptureStartMode.SYSTEM, false))
        assertNull(entries(null).single { it.key == MobileReadinessKey.CAPTURE }.ready)
    }

    @Test fun switchingToOfflineAddsItsOwnDownloadRequirementWithoutInventingARequirementForOnlineModels() {
        val online = Settings(translatorEngine = TranslatorEngine.GOOGLE, sourceLang = "en", targetLang = "ru")
        val models = MobileModelState(checking = false, ocrReady = true, translationReady = false)
        fun entries(settings: Settings, state: MobileModelState) = mobileReadinessItems(settings, state, true,
            dev.clickn.translate.capture.CaptureStartMode.SYSTEM, false, true, false, false, false)
        assertFalse(entries(online, models).any { it.key == MobileReadinessKey.TRANSLATION_MODELS })
        val offline = online.copy(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT)
        assertEquals(listOf(MobileReadinessKey.TRANSLATION_MODELS), entries(offline, models)
            .filter { it.required && it.ready != true }.map { it.key })
        assertTrue(entries(offline, models.copy(translationReady = true)).filter { it.required }.all { it.ready == true })
        assertEquals(entries(offline, models).size, entries(offline, models).map { it.key }.toSet().size)
    }

    @Test fun aFreshOrPartiallyPreparedScreenNeverClaimsItIsReady() {
        val online = Settings(translatorEngine = TranslatorEngine.GOOGLE, sourceLang = "auto", targetLang = "ru")
        val readyModels = MobileModelState(checking = false, ocrReady = true)
        assertTrue(mobileScreenReady(online, readyModels, overlay = true))
        assertFalse(mobileScreenReady(online, readyModels, overlay = false))
        assertFalse(mobileScreenReady(online, readyModels.copy(checking = true), overlay = true))
        assertFalse(mobileScreenReady(online, readyModels.copy(ocrReady = null), overlay = true))
        assertFalse(mobileScreenReady(online, readyModels.copy(ocrReady = false), overlay = true))
        assertFalse(mobileScreenReady(online.copy(translatorEngine = TranslatorEngine.OPENAI, apiKey = ""), readyModels, overlay = true))
    }

    @Test fun downloadedModelsDoNotMakeAnAutomaticOfflineSourceUsable() {
        val offline = Settings(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT, sourceLang = "auto", targetLang = "ru")
        val readyModels = MobileModelState(checking = false, ocrReady = true, translationReady = true)
        assertFalse(mobileScreenReady(offline, readyModels, overlay = true))
        val configured = offline.copy(sourceLang = "en")
        assertTrue(mobileScreenReady(configured, readyModels, overlay = true))
        assertFalse(mobileScreenReady(configured, readyModels.copy(translationReady = null), overlay = true))
        assertFalse(mobileScreenReady(configured, readyModels.copy(translationReady = false), overlay = true))
    }

    @Test fun credentialsAreRequiredForPaidServices() {
        listOf(TranslatorEngine.OPENAI, TranslatorEngine.ANTHROPIC, TranslatorEngine.DEEPL,
            TranslatorEngine.NIUTRANS, TranslatorEngine.YOUDAO_PICTRANS, TranslatorEngine.VOLC,
            TranslatorEngine.BAIDU_FANYI, TranslatorEngine.TENCENT).forEach {
            assertTrue(it.name, translationNeedsConfiguration(Settings(translatorEngine = it)))
        }
        assertFalse(translationNeedsConfiguration(Settings(translatorEngine = TranslatorEngine.GOOGLE)))
        assertFalse(translationNeedsConfiguration(Settings(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT)))
    }
    @Test fun configuredAndSelfHostedServicesRemainAvailable() {
        assertFalse(translationNeedsConfiguration(Settings(translatorEngine = TranslatorEngine.OPENAI, apiKey = "key", model = "model", baseUrl = "https://example.com")))
        assertTrue(translationNeedsConfiguration(Settings(translatorEngine = TranslatorEngine.OPENAI, apiKey = "key", model = "")))
        assertFalse(translationNeedsConfiguration(Settings(translatorEngine = TranslatorEngine.DEEPL, deeplProtocol = DeeplProtocol.DEEPLX, deeplBaseUrl = "http://localhost:1188")))
        assertTrue(translationNeedsConfiguration(Settings(translatorEngine = TranslatorEngine.DEEPL, deeplProtocol = DeeplProtocol.DEEPLX, deeplBaseUrl = "")))
    }
    @Test fun mlKitCanonicalLanguagesNeverBecomeASameLanguagePair() {
        val pair = mobileMlKitPair(Settings(sourceLang = "zh-CN", targetLang = "zh-TW"))
        assertEquals("zh", pair.targetLang)
        assertEquals("en", pair.sourceLang)
        assertEquals(TranslatorEngine.GOOGLE_ML_KIT, pair.translatorEngine)
        val selected = mobileLanguagePair(Settings(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT, sourceLang = "ru", targetLang = "zh-TW"), true, "zh-CN")
        assertEquals("zh-TW", selected.sourceLang)
        assertEquals("ru", selected.targetLang)
    }
    @Test fun unsupportedAndAutomaticSourcesGetAUsableOfflinePair() {
        val pair = mobileMlKitPair(Settings(sourceLang = "auto", targetLang = "en"))
        assertEquals("ru", pair.sourceLang)
        assertEquals("en", pair.targetLang)
        val norwegian = mobileMlKitPair(Settings(sourceLang = "nn", targetLang = "nb"))
        assertEquals("no", norwegian.targetLang)
        assertEquals("en", norwegian.sourceLang)
    }
}
