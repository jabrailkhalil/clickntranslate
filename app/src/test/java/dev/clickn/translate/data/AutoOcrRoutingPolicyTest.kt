// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import dev.clickn.translate.ocr.OcrLanguageCapability
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class AutoOcrRoutingPolicyTest {
    @Test fun detectedKoreanRoutesIndependentlyOfTranslationSource_tableDriven() {
        for (source in listOf("auto", "en", "ja", "zh-CN", "ko")) {
            val settings = Settings(sourceLang = source)
            val route = AutoOcrRoutingPolicy.resolve(settings, "ko") { true }!!
            assertEquals(source, OcrEngineKind.ML_KIT_KOREAN, route.engine)
            val effective = AutoOcrRoutingPolicy.settingsFor(settings, "ko", route)
            assertEquals("ko", effective.sourceLang)
            assertEquals(source, settings.sourceLang)
            assertEquals(settings.targetLang, effective.targetLang)
        }
    }

    @Test fun optionsKeepOnDeviceLocalHttpCloudOrder_tableDriven() {
        val expected = listOf(
            OcrEngineKind.ML_KIT_JAPANESE, OcrEngineKind.ML_KIT_KOREAN,
            OcrEngineKind.ML_KIT_CHINESE, OcrEngineKind.ML_KIT_LATIN,
            OcrEngineKind.PADDLE_ONNX, OcrEngineKind.MANGA_OCR_JA, OcrEngineKind.TESSERACT_ARABIC,
            OcrEngineKind.UMI_OCR, OcrEngineKind.LUNA_OCR,
            OcrEngineKind.BAIDU, OcrEngineKind.TENCENT, OcrEngineKind.YOUDAO,
            OcrEngineKind.PADDLE_AI_STUDIO,
        )
        assertEquals(OcrEngineKind.entries.toSet() - OcrEngineKind.ML_KIT_AUTO, expected.toSet())
        assertEquals(expected, AutoOcrRoutingPolicy.candidates.map { it.engine }.distinct())
        for (language in listOf("zh-CN", "zh-TW", "ja", "ko", "en", "fr", "ar", "nb", "ru")) {
            val options = AutoOcrRoutingPolicy.options(Settings(), language)
            val positions = options.map { expected.indexOf(it.engine) }
            assertEquals(language, positions.sorted(), positions)
            val paddleVersions = options.filter { it.engine == OcrEngineKind.PADDLE_ONNX }.map { it.paddleVersion }
            assertEquals(language, PaddleModelVersion.entries.filter { it in paddleVersions }, paddleVersions)
        }
    }

    @Test fun defaultLanguageMapping_tableDriven() {
        listOf(
            "zh-CN" to OcrEngineKind.ML_KIT_CHINESE,
            "zh-TW" to OcrEngineKind.ML_KIT_CHINESE,
            "JA_jp" to OcrEngineKind.ML_KIT_JAPANESE,
            "ko-KR" to OcrEngineKind.ML_KIT_KOREAN,
            "en-US" to OcrEngineKind.ML_KIT_LATIN,
            "fr" to OcrEngineKind.ML_KIT_LATIN,
            "sq" to OcrEngineKind.PADDLE_ONNX,
            "auto" to null,
            "ar" to OcrEngineKind.TESSERACT_ARABIC,
        ).forEach { (code, expected) -> assertEquals(code, expected, AutoOcrSettings().routeFor(code)?.engine) }
    }

    @Test fun capabilityOptions_tableDriven() {
        data class Case(val language: String, val route: AutoOcrRoute, val included: Boolean)
        listOf(
            Case("ja", AutoOcrRoute(OcrEngineKind.MANGA_OCR_JA), true),
            Case("ko", AutoOcrRoute(OcrEngineKind.MANGA_OCR_JA), false),
            Case("ko", AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V5_KOREAN), true),
            Case("ko", AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V6_SMALL), false),
            Case("ja", AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V6_TINY), false),
            Case("en", AutoOcrRoute(OcrEngineKind.ML_KIT_AUTO), false),
            Case("ru", AutoOcrRoute(OcrEngineKind.ML_KIT_LATIN), false),
        ).forEach { case ->
            assertEquals(case.toString(), case.included, case.route in AutoOcrRoutingPolicy.options(Settings(), case.language))
        }
    }

    @Test fun missingModelInvalidMappingAndCloudCredentials_tableDriven() {
        val cloud = AutoOcrRoute(OcrEngineKind.YOUDAO)
        val manga = AutoOcrRoute(OcrEngineKind.MANGA_OCR_JA)
        data class Case(val route: AutoOcrRoute, val installed: Boolean, val keys: Boolean, val expected: OcrEngineKind)
        listOf(
            Case(manga, true, false, OcrEngineKind.MANGA_OCR_JA),
            Case(manga, false, false, OcrEngineKind.ML_KIT_JAPANESE),
            Case(cloud, true, false, OcrEngineKind.ML_KIT_JAPANESE),
            Case(cloud, true, true, OcrEngineKind.YOUDAO),
            Case(AutoOcrRoute(OcrEngineKind.ML_KIT_KOREAN), true, false, OcrEngineKind.ML_KIT_JAPANESE),
        ).forEach { case ->
            val settings = Settings(autoOcr = AutoOcrSettings(mapOf("ja" to case.route)),
                youdaoAppKey = if (case.keys) "test-key" else "", youdaoAppSecret = if (case.keys) "test-secret" else "")
            assertEquals(case.toString(), case.expected, AutoOcrRoutingPolicy.resolve(settings, "ja") {
                it.engine != OcrEngineKind.MANGA_OCR_JA || case.installed
            }?.engine)
        }
        assertEquals(AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V5_ARABIC),
            AutoOcrRoutingPolicy.resolve(Settings(), "ar") { true })
        assertNull(AutoOcrRoutingPolicy.resolve(Settings(), "ar") { false })
    }

    @Test fun arabicDefaultUsesOnlyActuallyReadyLocalPacks() {
        val paddle = AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V5_ARABIC)
        val tess = AutoOcrRoute(OcrEngineKind.TESSERACT_ARABIC)
        for ((installed, expected) in listOf(
            emptySet<AutoOcrRoute>() to null,
            setOf(tess) to tess,
            setOf(paddle) to paddle,
            setOf(tess, paddle) to paddle,
        )) {
            val checked = mutableListOf<AutoOcrRoute>()
            val settings = Settings(baiduOcrApiKey = "unused", baiduOcrSecretKey = "unused")
            val actual = AutoOcrRoutingPolicy.resolve(settings, "ar-EG") {
                checked += it
                it in installed
            }
            assertEquals(installed.toString(), expected, actual)
            assertTrue("Automatic fallback must not consider cloud or another Paddle pack",
                checked.all { it == paddle || it == tess })
        }
        assertEquals(tess, AutoOcrSettings.defaultRoute("ar"))
        assertEquals(paddle, AutoOcrSettings.defaultRoute("ar", arabicPaddleReady = true))
        assertEquals(AutoOcrRoute(OcrEngineKind.ML_KIT_LATIN),
            AutoOcrSettings.defaultRoute("en", arabicPaddleReady = true))
    }

    @Test fun persistedExplicitTesseractSurvivesInstallingPreferredArabicPaddle() {
        val restored = Json.decodeFromString<Settings>(
            """{"autoOcr":{"routes":{"ar":{"engine":"TESSERACT_ARABIC"}}}}""")
        val explicit = AutoOcrRoute(OcrEngineKind.TESSERACT_ARABIC)
        assertEquals(explicit, restored.autoOcr.routeFor("ar-SA", arabicPaddleReady = true))
        val checked = mutableListOf<AutoOcrRoute>()
        assertEquals(explicit, AutoOcrRoutingPolicy.resolve(restored, "ar-SA") {
            checked += it
            true // Both local engines are installed; the persisted override still wins.
        })
        assertEquals(listOf(explicit), checked)
        assertEquals(explicit, restored.autoOcr.routes["ar"])
        assertEquals("ar", AutoOcrRoutingPolicy.settingsFor(restored, "ar-SA", explicit).sourceLang)
    }

    @Test fun unavailableArabicOverrideFallsBackLocallyWithoutSelectingUnconfiguredCloud() {
        val paddle = AutoOcrRoute(OcrEngineKind.PADDLE_ONNX, PaddleModelVersion.V5_ARABIC)
        val tess = AutoOcrRoute(OcrEngineKind.TESSERACT_ARABIC)
        for (selectedRoute in listOf(paddle, AutoOcrRoute(OcrEngineKind.BAIDU))) {
            val settings = Settings(autoOcr = AutoOcrSettings(mapOf("ar" to selectedRoute)))
            assertEquals(tess, AutoOcrRoutingPolicy.resolve(settings, "ar") { it == tess })
            assertNull(AutoOcrRoutingPolicy.resolve(settings, "ar") { false })
            assertEquals(selectedRoute, settings.autoOcr.routes["ar"])
        }
    }

    @Test fun mappingRoundTripPresetAndCredentialBoundary() {
        val config = AutoOcrSettings(mapOf("ja-JP" to AutoOcrRoute(OcrEngineKind.MANGA_OCR_JA),
            "auto" to AutoOcrRoute(OcrEngineKind.ML_KIT_AUTO))).normalized()
        assertEquals(setOf("ja"), config.routes.keys)
        val settings = Settings(autoOcr = config, apiKey = "must-not-export")
        val json = Json.encodeToString(AutoOcrSettings.serializer(), config)
        assertEquals(config, Json.decodeFromString<AutoOcrSettings>(json))
        val portable = SettingsFieldPolicy.encodePortable(settings)
        assertFalse(portable.toString().contains("must-not-export"))
        assertFalse(portable.containsKey("autoOcr"))
        assertEquals(AutoOcrSettings(), SettingsFieldPolicy.decodePortable(portable).settings.autoOcr)
        val preset = TranslationPresetCatalog.fromSettings("test-auto", "Auto", "Auto", settings)
        assertEquals(AutoOcrSettings(), preset.applyTo(Settings()).autoOcr)
        assertEquals(config, preset.applyTo(settings).autoOcr)
        assertEquals(OcrEngineKind.ML_KIT_AUTO, settings.ocrEngine)
        assertEquals(PaddleModelVersion.V6_SMALL,
            AutoOcrRoutingPolicy.settingsFor(settings, "ja", config.routeFor("ja")!!).paddleModelVersion)
        assertTrue(OcrLanguageCapability.supports(settings, "ja"))
        assertTrue(OcrEngineKind.ML_KIT_AUTO.needsRawBitmap)
    }

    @Test fun automaticCloudLanguageDoesNotReuseAnotherLanguageOrMutateManualSettings() {
        val manual = Settings(baiduOcrLanguage = BaiduOcrLanguage.JAP, tencentOcrLanguage = TencentOcrLanguage.JA)
        for (language in listOf("zh-CN", "zh-TW", "en", "ja", "ko")) {
            for (engine in listOf(OcrEngineKind.BAIDU, OcrEngineKind.TENCENT)) {
                assertTrue("$engine $language", AutoOcrRoutingPolicy.supports(manual, language, AutoOcrRoute(engine)))
            }
        }
        assertTrue(AutoOcrRoutingPolicy.supports(manual, "no", AutoOcrRoute(OcrEngineKind.TENCENT)))
        assertTrue(AutoOcrRoutingPolicy.supports(manual, "nb", AutoOcrRoute(OcrEngineKind.TENCENT)))
        assertEquals(BaiduOcrLanguage.JAP, manual.baiduOcrLanguage)
        assertEquals(TencentOcrLanguage.JA, manual.tencentOcrLanguage)
    }
}
