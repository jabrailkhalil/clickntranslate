package dev.clickn.translate.ocr

import dev.clickn.translate.data.AutoOcrRoute
import dev.clickn.translate.data.AutoOcrRoutingPolicy
import dev.clickn.translate.data.AutoOcrSettings
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.PaddleModelVersion
import dev.clickn.translate.data.Settings
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class TesseractIntegrationPolicyTest {
    @Test fun arabicWithoutAnyAccountGetsALocalRecommendationAndMixedAutoStaysLocal() {
        for (source in listOf("ar", "ar-EG", "AR-sa")) {
            val recommendation = OcrLanguageCapability.recommendFor(source, Settings())!!
            assertEquals(OcrEngineKind.TESSERACT_ARABIC, recommendation.engine)
            assertFalse(recommendation.keysMissing)
            assertTrue(OcrLanguageCapability.supports(Settings(ocrEngine = recommendation.engine), source))
            assertTrue(requiresArabicOcrBootstrap(Settings(sourceLang = source)))
        }
        val mixed = Settings(ocrEngine = OcrEngineKind.TESSERACT_ARABIC, sourceLang = "auto")
        assertTrue(OcrLanguageCapability.supports(mixed, "auto"))
        assertNull(OcrLanguageCapability.recommendFor("auto", mixed))
        for (source in listOf("ja", "ru", "fa", "ur", "fr", "he"))
            assertFalse(source, OcrLanguageCapability.supports(mixed, source))
        assertTrue(OcrLanguageCapability.supports(mixed, "en-US"))
    }

    @Test fun explicitPaidArabicSelectionIsPreservedRatherThanSilentlyChangingProviders() {
        val selected = Settings(ocrEngine = OcrEngineKind.BAIDU, baiduOcrApiKey = "owned-key", baiduOcrSecretKey = "owned-secret")
        val recommendation = OcrLanguageCapability.recommendFor("ar", selected)!!
        assertEquals(OcrEngineKind.BAIDU, recommendation.engine)
        assertFalse(recommendation.keysMissing)
    }

    @Test fun arabicAutoRouteRequiresActualReadinessAndCannotFallBackToAnUnselectedCloud() {
        val settings = Settings(sourceLang = "ar", baiduOcrApiKey = "unused-key", baiduOcrSecretKey = "unused-secret")
        val seen = mutableListOf<AutoOcrRoute>()
        assertNull(AutoOcrRoutingPolicy.resolve(settings, "ar") { seen += it; false })
        assertTrue(seen.isNotEmpty())
        assertTrue(seen.all { it.engine == OcrEngineKind.TESSERACT_ARABIC ||
            it == AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V5_ARABIC) })
        val resolved = AutoOcrRoutingPolicy.resolve(settings, "ar-EG") { it.engine == OcrEngineKind.TESSERACT_ARABIC }!!
        assertEquals(OcrEngineKind.TESSERACT_ARABIC, resolved.engine)
        val effective = AutoOcrRoutingPolicy.settingsFor(settings, "ar-EG", resolved)
        assertEquals("ar", effective.sourceLang)
        assertEquals(settings.targetLang, effective.targetLang)
        assertEquals("ar", settings.sourceLang)
    }

    @Test fun modelAdmissionAddsARealArabicCandidateWithoutRenamingMlKitOrDroppingOtherScripts() {
        val without = autoOcrBootstrapEngines(false)
        assertFalse(OcrEngineKind.TESSERACT_ARABIC in without)
        val installed = autoOcrBootstrapEngines(true)
        assertEquals(without, installed.filterNot { it == OcrEngineKind.TESSERACT_ARABIC })
        assertEquals(1, installed.count { it == OcrEngineKind.TESSERACT_ARABIC })
        assertFalse(requiresArabicOcrBootstrap(Settings(sourceLang = "auto")))
        assertFalse(requiresArabicOcrBootstrap(Settings(sourceLang = "en")))
        // Candidate evidence competes per region; an Arabic paragraph must survive beside Latin.
        data class Region(val row: Int, val evidence: AutoOcrEvidence)
        val arabic = Region(1, AutoOcrEvidence("مرحبا بكم في تطبيق الترجمة", "ar", .95f))
        val latin = Region(2, AutoOcrEvidence("Welcome to the translation app", "en", .9f))
        val misread = Region(1, AutoOcrEvidence("I I I", null, .1f))
        val selected = selectAutoOcrRegions(listOf(misread, latin, arabic), { it.evidence }, { a, b -> a.row == b.row })
        assertEquals(setOf(arabic, latin), selected.toSet())
    }

    @Test fun enumAppendsWithoutChangingDefaultsAndOldSettingsStillDecode() {
        assertEquals(OcrEngineKind.ML_KIT_AUTO, Settings().ocrEngine)
        assertEquals(OcrEngineKind.ML_KIT_AUTO, Json.decodeFromString<Settings>("{}").ocrEngine)
        val settings = Settings(ocrEngine = OcrEngineKind.TESSERACT_ARABIC, sourceLang = "auto",
            autoOcr = AutoOcrSettings(mapOf("ar" to AutoOcrRoute(OcrEngineKind.TESSERACT_ARABIC))))
        assertEquals(settings, Json.decodeFromString<Settings>(Json.encodeToString(settings)))
    }
}
