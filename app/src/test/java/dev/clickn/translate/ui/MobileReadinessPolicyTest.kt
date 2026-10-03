package dev.clickn.translate.ui

import dev.clickn.translate.data.*
import org.junit.Assert.*
import org.junit.Test

class MobileReadinessPolicyTest {
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
