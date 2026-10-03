// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import android.content.Context
import android.graphics.Typeface
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureRegionBorderStyle
import dev.clickn.translate.capture.normalizedCaptureRegionBorderWidthDp
import dev.clickn.translate.data.FloatingMenu
import dev.clickn.translate.data.InputTranslationDoubleAction
import dev.clickn.translate.data.MangaOcrAdvancedSettingsPolicy
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.OpenAiRequestOptions
import dev.clickn.translate.data.OverlayFontEntry
import dev.clickn.translate.data.OverlayFontCommit
import dev.clickn.translate.data.OverlayTextStyle
import dev.clickn.translate.data.OverlayFontImportResult
import dev.clickn.translate.data.OverlayFontManager
import dev.clickn.translate.data.OverlayPlacement
import dev.clickn.translate.data.OverlayTheme
import dev.clickn.translate.data.PreprocessOptions
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.normalizedFloatingButtonAlpha
import dev.clickn.translate.data.SettingsBundleExportResult
import dev.clickn.translate.data.SettingsBundleImportResult
import dev.clickn.translate.data.SettingsBundlePreview
import dev.clickn.translate.data.SettingsBundleTransfer
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.data.StagedOverlayFont
import dev.clickn.translate.data.TranslationPreset
import dev.clickn.translate.data.TranslationContextMode
import dev.clickn.translate.data.TranslationBlockInteractionMode
import dev.clickn.translate.data.TranslationPresetCatalog
import dev.clickn.translate.data.TranslationPresetImportResult
import dev.clickn.translate.data.TranslationPresetTransfer
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.data.TtsHttpResponseMode
import dev.clickn.translate.data.TtsProvider
import dev.clickn.translate.data.VolcengineTtsResource
import dev.clickn.translate.data.MiniMaxTtsModel
import dev.clickn.translate.data.MimoTtsModel
import dev.clickn.translate.data.MAX_TTS_PLAYBACK_GAIN_DB
import dev.clickn.translate.data.MIN_TTS_PLAYBACK_GAIN_DB
import dev.clickn.translate.download.ModelDownloadManager
import dev.clickn.translate.download.ModelDownloadNetworkProbeResult
import dev.clickn.translate.download.ModelDownloadNetworkTester
import dev.clickn.translate.download.ModelReadinessChecker
import dev.clickn.translate.download.ModelDownloadSpec
import dev.clickn.translate.glossary.TranslationGlossaryRepository
import dev.clickn.translate.llm.LlmModelInstaller
import dev.clickn.translate.llm.LlmModelKind
import dev.clickn.translate.ocr.OrientationModelInstaller
import dev.clickn.translate.ocr.PaddleModelInstaller
import dev.clickn.translate.ocr.lunaOcrHttpHostOrNull
import dev.clickn.translate.ocr.umiOcrHttpHostOrNull
import dev.clickn.translate.translate.RoutingTranslator
import dev.clickn.translate.translate.TestResult
import dev.clickn.translate.tts.ttsHttpHostOrNull
import dev.clickn.translate.tts.ttsApiHttpHostOrNull
import dev.clickn.translate.tts.SystemTtsEngine
import dev.clickn.translate.tts.SystemTtsVoiceOption
import dev.clickn.translate.tts.settingsForTtsTest
import dev.clickn.translate.tts.TtsEngine
import dev.clickn.translate.tts.HttpTtsEngine
import dev.clickn.translate.tts.VoiceDesignPromptGenerator
import dev.clickn.translate.tts.MiniMaxManagedVoice
import dev.clickn.translate.tts.MiniMaxVoiceCloneRequest
import dev.clickn.translate.tts.MiniMaxVoiceCreationResult
import dev.clickn.translate.tts.MiniMaxVoiceDesignRequest
import dev.clickn.translate.tts.MiniMaxVoiceManager
import dev.clickn.translate.tts.decodeMiniMaxTrialAudio
import androidx.work.WorkInfo
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext

@HiltViewModel
class SettingsViewModel @Inject constructor(
    @ApplicationContext private val appContext: Context,
    private val repo: SettingsRepository,
    private val paddleInstaller: PaddleModelInstaller,
    private val mangaOcrInstaller: dev.clickn.translate.ocr.MangaOcrModelInstaller,
    private val orientationModelInstaller: OrientationModelInstaller,
    private val routingTranslator: RoutingTranslator,
    private val connectionTester: dev.clickn.translate.translate.TranslatorConnectionTester,
    private val llmInstaller: LlmModelInstaller,
    private val modelReadinessChecker: ModelReadinessChecker,
    private val overlayFontManager: OverlayFontManager,
    private val glossaryRepository: TranslationGlossaryRepository,
    private val modelDownloadManager: ModelDownloadManager,
    private val modelDownloadNetworkTester: ModelDownloadNetworkTester,
    private val systemTtsEngine: SystemTtsEngine,
    private val ttsEngine: TtsEngine,
    private val httpTtsEngine: HttpTtsEngine,
    private val voiceDesignPromptGenerator: VoiceDesignPromptGenerator,
    private val miniMaxVoiceManager: MiniMaxVoiceManager,
    private val appPermissions: dev.clickn.translate.shizuku.AppPermissionCoordinator,
) : ViewModel() {

    val modelDownloadWorkInfos: Flow<List<WorkInfo>> = modelDownloadManager.workInfos

    suspend fun load(): Settings = repo.get()

    private var localeChangeDraft: Settings? = null
    internal fun retainLocaleChangeDraft(value: Settings?) { localeChangeDraft = value }
    internal fun consumeLocaleChangeDraft(): Settings? = localeChangeDraft.also { localeChangeDraft = null }

    private val recentLanguageMutex = Mutex()

    internal fun rememberMlKitSourceLanguage(languageTag: String) =
        viewModelScope.launch(start = CoroutineStart.UNDISPATCHED) {
            recentLanguageMutex.withLock {
                withContext(Dispatchers.IO) {
                    repo.update { current ->
                        current.copy(mlKitRecentSourceLanguages = mlKitRecentSourceLanguages(
                            current.mlKitRecentSourceLanguages, languageTag,
                        ))
                    }
                }
            }
        }

    private val autoOcrSettingsSaver by lazy {
        AutoOcrSettingsSaver(viewModelScope) { value ->
            withContext(Dispatchers.IO) { repo.update { it.copy(autoOcr = value) } }
        }
    }
    internal fun saveAutoOcrSettings(value: dev.clickn.translate.data.AutoOcrSettings) =
        autoOcrSettingsSaver.save(value)

    internal suspend fun availableAutoOcrRoutes(settings: Settings): Set<dev.clickn.translate.data.AutoOcrRoute> =
        withContext(Dispatchers.IO) {
            dev.clickn.translate.data.AutoOcrRoutingPolicy.candidates.filter { route ->
                dev.clickn.translate.data.AutoOcrRoutingPolicy.configured(settings, route) && when (route.engine) {
                    OcrEngineKind.PADDLE_ONNX -> modelReadinessChecker.paddle(route.paddleVersion).ready
                    OcrEngineKind.MANGA_OCR_JA -> modelReadinessChecker.mangaOcr().ready
                    else -> true
                }
            }.toSet()
        }

    suspend fun loadForScreen(activityContext: Context): Settings = withContext(Dispatchers.IO) {
        loadSettingsForScreen(
            read = repo::get,
            update = repo::update,
            currentDefault = activityContext.getString(R.string.default_prompt),
            knownDefaults = {
                listOf("zh-CN", "en").map { tag ->
                    val cfg = android.content.res.Configuration(activityContext.resources.configuration)
                        .apply { setLocale(java.util.Locale.forLanguageTag(tag)) }
                    activityContext.createConfigurationContext(cfg).getString(R.string.default_prompt)
                }
            },
        )
    }

    private val floatingButtonSettingsSaver by lazy {
        FloatingButtonSettingsSaver(viewModelScope) { value ->
            withContext(Dispatchers.IO) { repo.update(value::applyTo) }
        }
    }

    internal fun saveFloatingButtonSettings(value: FloatingButtonSettings) =
        floatingButtonSettingsSaver.save(value)

    internal suspend fun loadModelStates(request: SettingsModelReadinessRequest) = withContext(Dispatchers.IO) {
        checkSettingsModels(request, ::llmModelUiState, ::paddleModelUiState,
            ::mangaOcrModelUiState, ::orientationModelUiState)
    }

    suspend fun enableAccessibilityViaShizuku(): Boolean = appPermissions.configureIfReady().accessibilityConnected

    suspend fun downloadMlKitLanguagePair(sourceLang: String, targetLang: String, timeoutSeconds: Int) {
        routingTranslator.downloadMlKitLanguagePair(sourceLang, targetLang, timeoutSeconds)
    }

    internal suspend fun testModelDownloadNetwork(): List<ModelDownloadNetworkProbeResult> =
        modelDownloadNetworkTester.probeConfiguredSources()

    suspend fun areMlKitLanguagePairModelsDownloaded(
        sourceLang: String,
        targetLang: String,
    ): Boolean = routingTranslator.areMlKitLanguagePairModelsDownloaded(sourceLang, targetLang)

    suspend fun getMissingMlKitLanguageModels(
        sourceLang: String,
        targetLang: String,
    ): Set<String> = routingTranslator.getMissingMlKitLanguageModels(sourceLang, targetLang)

    suspend fun getDownloadedMlKitLanguageModels(): Set<String> =
        routingTranslator.getDownloadedMlKitLanguageModels()

    suspend fun deleteMlKitSourceLanguageModel(sourceLang: String, targetLang: String) =
        routingTranslator.deleteMlKitSourceLanguageModel(sourceLang, targetLang)

    suspend fun loadSystemTtsVoices(preferredLanguageTag: String): List<SystemTtsVoiceOption> =
        systemTtsEngine.availableVoices(preferredLanguageTag)

    suspend fun testTts(text: String, settings: Settings) {
        require(text.isNotBlank()) { "TTS test text is blank" }
        ttsEngine.stop()
        ttsEngine.speak(text, settingsForTtsTest(text, settings))
    }

    fun stopTts() = ttsEngine.stop()

    internal suspend fun loadMiniMaxManagedVoices(
        baseUrl: String,
        apiKey: String,
    ): List<MiniMaxManagedVoice> = miniMaxVoiceManager.loadVoices(baseUrl, apiKey)

    internal suspend fun cloneMiniMaxVoice(
        request: MiniMaxVoiceCloneRequest,
    ): MiniMaxVoiceCreationResult = miniMaxVoiceManager.cloneVoice(request)

    internal suspend fun designMiniMaxVoice(
        request: MiniMaxVoiceDesignRequest,
    ): MiniMaxVoiceCreationResult = miniMaxVoiceManager.designVoice(request)

    internal suspend fun playMiniMaxTrialAudio(audioHex: String, gainDb: Int) {
        val payload = decodeMiniMaxTrialAudio(audioHex)
        ttsEngine.stop()
        httpTtsEngine.playAudio(
            payload = payload,
            playbackId = "minimax-voice-design-trial",
            gainDb = gainDb,
        )
    }

    internal suspend fun deleteMiniMaxVoice(
        baseUrl: String,
        apiKey: String,
        voice: MiniMaxManagedVoice,
    ) = miniMaxVoiceManager.deleteVoice(baseUrl, apiKey, voice)

    suspend fun generateMimoVoiceDesign(
        draft: String,
        settings: Settings,
        outputLanguageTag: String,
    ): String = voiceDesignPromptGenerator.generate(draft, settings, outputLanguageTag)

    suspend fun generateMiniMaxVoiceDescription(
        draft: String,
        settings: Settings,
        outputLanguageTag: String,
    ): String = voiceDesignPromptGenerator.generateMiniMaxDescription(
        draft,
        settings,
        outputLanguageTag,
    )

    suspend fun polishMimoStyleInstruction(
        draft: String,
        settings: Settings,
        outputLanguageTag: String,
    ): String = voiceDesignPromptGenerator.polishStyleInstruction(
        draft,
        settings,
        outputLanguageTag,
    )

    suspend fun exportSettingsBundle(
        uri: Uri,
        settings: Settings,
    ): SettingsBundleExportResult = withContext(Dispatchers.IO) {
        val output = appContext.contentResolver.openOutputStream(uri, "w")
            ?: error("Could not open the selected export file.")
        output.use {
            SettingsBundleTransfer.write(
                output = it,
                settings = settings,
                resolveFontFile = overlayFontManager::transferFileFor,
                glossaryTerms = glossaryRepository.listAll(),
            )
        }
    }

    suspend fun previewSettingsBundle(uri: Uri): SettingsBundlePreview = withContext(Dispatchers.IO) {
        val input = appContext.contentResolver.openInputStream(uri)
            ?: error("Could not open the selected settings file.")
        input.use(SettingsBundleTransfer::readPreview)
    }

    suspend fun importSettingsBundle(uri: Uri): SettingsBundleImportResult = withContext(Dispatchers.IO) {
        val stagingDir = File(appContext.cacheDir, "settings-import-${System.nanoTime()}")
        require(stagingDir.mkdirs()) { "Could not create settings import staging storage." }
        val stagedFonts = mutableListOf<StagedOverlayFont>()
        val commits = mutableListOf<OverlayFontCommit>()
        try {
            val input = appContext.contentResolver.openInputStream(uri)
                ?: error("Could not open the selected settings file.")
            val preview = input.use { source ->
                SettingsBundleTransfer.read(source) { font, fontInput ->
                    stagedFonts += overlayFontManager.stageTransferredFont(font, fontInput, stagingDir)
                }
            }
            if (preview.legacyPresetOnly) {
                val imported = importTranslationPresets(preview.presets)
                return@withContext SettingsBundleImportResult(
                    settings = repo.get(),
                    importedPresetCount = imported.importedCount,
                    overwrittenPresetNames = imported.overwrittenNames,
                    importedFontCount = 0,
                    importedGlossaryTermCount = 0,
                    legacyPresetOnly = true,
                    skippedSettingFieldCount = 0,
                )
            }

            val importedSettings = requireNotNull(preview.settings)
            val beforeSettings = repo.get()
            val beforeGlossary = glossaryRepository.listAll()
            var glossaryCommitted = false
            var settingsCommitted = false
            try {
                stagedFonts.forEach { commits += overlayFontManager.commitTransferredFont(it) }
                val installedFonts = commits.map(OverlayFontCommit::entry)
                val availableFonts = overlayFontManager.existingFontEntries(
                    beforeSettings.overlayFonts + importedSettings.overlayFonts + installedFonts,
                )
                val merged = SettingsBundleTransfer.mergeImportedSettings(
                    current = beforeSettings,
                    imported = importedSettings,
                    availableFonts = availableFonts,
                )
                val importedGlossaryCount = glossaryRepository.importTerms(preview.glossaryTerms)
                glossaryCommitted = true
                val importedState = repo.updateAfterPresetImport(
                    (merged.presetResult.addedNames + merged.presetResult.overwrittenNames).toSet(),
                ) { merged.settings }
                settingsCommitted = true
                commits.forEach(overlayFontManager::finishTransferredFont)
                SettingsBundleImportResult(
                    settings = importedState,
                    importedPresetCount = merged.presetResult.importedCount,
                    overwrittenPresetNames = merged.presetResult.overwrittenNames,
                    importedFontCount = installedFonts.size,
                    importedGlossaryTermCount = importedGlossaryCount,
                    legacyPresetOnly = false,
                    skippedSettingFieldCount = preview.skippedSettingFields.size,
                )
            } catch (error: Throwable) {
                if (settingsCommitted) {
                    runCatching { repo.update { beforeSettings } }.exceptionOrNull()?.let(error::addSuppressed)
                }
                if (glossaryCommitted) {
                    runCatching { glossaryRepository.restoreTerms(beforeGlossary) }
                        .exceptionOrNull()?.let(error::addSuppressed)
                }
                commits.asReversed().forEach { commit ->
                    runCatching { overlayFontManager.rollbackTransferredFont(commit) }
                        .exceptionOrNull()?.let(error::addSuppressed)
                }
                throw error
            }
        } finally {
            stagingDir.deleteRecursively()
        }
    }

    suspend fun importOverlayFont(uri: Uri): OverlayFontImportResult =
        overlayFontManager.importFont(uri)

    suspend fun resetOverlayFont() {
        overlayFontManager.resetFont()
    }

    suspend fun selectOverlayFont(fileName: String, displayName: String): Boolean =
        overlayFontManager.selectFont(fileName, displayName)

    suspend fun deleteOverlayFont(fileName: String): Boolean =
        overlayFontManager.deleteFont(fileName)

    fun overlayTypefaceFor(fileName: String): Typeface? =
        overlayFontManager.typefaceFor(fileName)

    @Suppress("LongParameterList")
    suspend fun save(
        baseUrl: String,
        apiKey: String,
        model: String,
        anthropicBaseUrl: String,
        anthropicApiKey: String,
        anthropicModel: String,
        targetLang: String,
        sourceLang: String,
        prompt: String,
        openAiRequestOptions: OpenAiRequestOptions,
        textSize: Int,
        overlayTextStyle: OverlayTextStyle,
        alpha: Float,
        loopMs: Long,
        loopTriggerMode: dev.clickn.translate.data.LoopTriggerMode,
        loopTextStableDurationMs: Long,
        loopSkipSimilarFrames: Boolean,
        loopFrameSimilarityThreshold: Float,
        loopTextRegionMode: dev.clickn.translate.data.LoopTextRegionMode,
        loopTranslateRegionOnly: Boolean,
        developerOptionsEnabled: Boolean,
        performanceOverlayEnabled: Boolean,
        ocrScreenshotSavingEnabled: Boolean,
        disableTranslationCache: Boolean,
        batchCumulativeCompletionTimeEnabled: Boolean,
        shareEntireScreen: Boolean,
        ocrRedBoxModeEnabled: Boolean,
        ocrRedBoxShowSourceText: Boolean,
        ocrRedBoxShowTranslation: Boolean,
        streaming: Boolean,
        retryFailedTranslation: Boolean,
        ttsEnabled: Boolean,
        ttsProvider: TtsProvider,
        ttsVoice: String,
        ttsEmotion: String,
        ttsSpeed: Float,
        ttsPitch: Float,
        ttsGainDb: Int,
        ttsHttpBaseUrl: String,
        ttsHttpBearerToken: String,
        ttsHttpResponseMode: TtsHttpResponseMode,
        ttsVolcengineResource: VolcengineTtsResource,
        ttsVolcengineBaseUrl: String,
        ttsVolcengineApiKey: String,
        ttsVolcengineSpeaker: String,
        ttsVolcengineModel: String,
        ttsVolcengineContext: String,
        ttsVolcenginePitch: Int,
        ttsVolcengineToneFidelity: Boolean,
        ttsMiniMaxModel: MiniMaxTtsModel,
        ttsMiniMaxBaseUrl: String,
        ttsMiniMaxApiKey: String,
        ttsMiniMaxVoice: String,
        ttsMiniMaxEmotion: String,
        ttsMiniMaxSpeed: Float,
        ttsMiniMaxPitch: Int,
        ttsMimoModel: MimoTtsModel,
        ttsMimoBaseUrl: String,
        ttsMimoApiKey: String,
        ttsMimoVoice: String,
        ttsMimoInstruction: String,
        ttsMimoVoiceDesignPrompt: String,
        ttsMimoVoiceCloneInstruction: String,
        ttsMimoVoiceSampleUri: String,
        renderMode: RenderMode,
        translationBlockInteractionMode: TranslationBlockInteractionMode,
        placement: OverlayPlacement,
        overlayStyleMode: dev.clickn.translate.data.OverlayStyleMode,
        overlayTheme: OverlayTheme,
        customBg: Int,
        customFg: Int,
        customBorder: Int,
        customBorderW: Int,
        offsetX: Int,
        offsetY: Int,
        ocrEngine: OcrEngineKind,
        autoOcr: dev.clickn.translate.data.AutoOcrSettings,
        baiduKey: String,
        baiduSecret: String,
        baiduEndpoint: dev.clickn.translate.data.BaiduOcrEndpoint,
        baiduLanguage: dev.clickn.translate.data.BaiduOcrLanguage,
        umiOcrBaseUrl: String,
        lunaOcrBaseUrl: String,
        paddleAiStudioToken: String,
        tencentId: String,
        tencentKey: String,
        tencentRegion: String,
        tencentEndpoint: dev.clickn.translate.data.TencentOcrEndpoint,
        tencentLanguage: dev.clickn.translate.data.TencentOcrLanguage,
        preprocess: PreprocessOptions,
        a11yVolume: Boolean,
        floatingButtonSizeDp: Int,
        floatingButtonAlpha: Float,
        floatingButtonSnapToEdge: Boolean,
        floatingButtonAutoDock: Boolean,
        floatingButtonDockInsetDp: Int,
        allowWrap: Boolean,
        avoidCollision: Boolean,
        apiTimeoutSeconds: Int,
        mergeAdjacentBlocks: Boolean,
        mergeStrength: dev.clickn.translate.data.MergeStrength,
        translationContextMode: TranslationContextMode,
        cleartextAllowedHosts: List<String>,
        translatorEngine: TranslatorEngine,
        deeplKey: String,
        deeplPro: Boolean,
        deeplProtocol: dev.clickn.translate.data.DeeplProtocol,
        deeplBaseUrl: String,
        deeplBearerAuth: Boolean,
        deeplCustomToken: String,
        niuTransMode: dev.clickn.translate.data.NiuTransMode,
        niuTransApiKey: String,
        niuTransAppId: String,
        niuTransTermLibraryId: String,
        niuTransMemoryLibraryId: String,
        youdaoAppKey: String,
        youdaoAppSecret: String,
        volcAccessKeyId: String,
        volcSecretAccessKey: String,
        volcRegion: String,
        baiduFanyiAppId: String,
        baiduFanyiSecretKey: String,
        overlayFonts: List<OverlayFontEntry>,
        activeTranslationPresetId: String,
    ) {
        repo.update {
            it.copy(
                baseUrl = baseUrl.trim(),
                apiKey = apiKey.trim(),
                model = model.trim(),
                anthropicBaseUrl = anthropicBaseUrl.trim(),
                anthropicApiKey = anthropicApiKey.trim(),
                anthropicModel = anthropicModel.trim(),
                targetLang = targetLang.trim(),
                sourceLang = sourceLang.trim(),
                promptTemplate = prompt,
                openAiRequestOptions = openAiRequestOptions.normalized(),
                overlayTextSizeSp = textSize.coerceIn(10, 28),
                overlayTextStyle = overlayTextStyle.normalized(),
                overlayAlpha = alpha.coerceIn(0.3f, 1f),
                captureLoopIntervalMs = loopMs.coerceAtLeast(200),
                loopTriggerMode = loopTriggerMode,
                loopTextStableDurationMs = loopTextStableDurationMs.coerceIn(200L, 2000L),
                loopSkipSimilarFrames = loopSkipSimilarFrames,
                loopFrameSimilarityThreshold = loopFrameSimilarityThreshold.coerceIn(0.50f, 0.99f),
                loopTextRegionMode = loopTextRegionMode,
                loopTranslateRegionOnly = loopTranslateRegionOnly,
                developerOptionsEnabled = developerOptionsEnabled,
                performanceOverlayEnabled = performanceOverlayEnabled,
                ocrScreenshotSavingEnabled = ocrScreenshotSavingEnabled,
                disableTranslationCache = disableTranslationCache,
                batchCumulativeCompletionTimeEnabled = batchCumulativeCompletionTimeEnabled,
                shareEntireScreen = shareEntireScreen,
                ocrRedBoxModeEnabled = ocrRedBoxModeEnabled,
                ocrRedBoxShowSourceText = ocrRedBoxShowSourceText,
                ocrRedBoxShowTranslation = ocrRedBoxShowTranslation,
                streamingTranslate = streaming,
                retryFailedTranslation = retryFailedTranslation,
                ttsEnabled = ttsEnabled,
                ttsProvider = ttsProvider,
                ttsVoice = ttsVoice.trim(),
                ttsEmotion = ttsEmotion.trim(),
                ttsSpeed = ttsSpeed.coerceIn(0.25f, 4.0f),
                ttsPitch = ttsPitch.coerceIn(0.25f, 4.0f),
                ttsGainDb = ttsGainDb.coerceIn(
                    MIN_TTS_PLAYBACK_GAIN_DB,
                    MAX_TTS_PLAYBACK_GAIN_DB,
                ),
                ttsHttpBaseUrl = ttsHttpBaseUrl.trim(),
                ttsHttpBearerToken = ttsHttpBearerToken.trim(),
                ttsHttpResponseMode = ttsHttpResponseMode,
                ttsVolcengineResource = ttsVolcengineResource,
                ttsVolcengineBaseUrl = ttsVolcengineBaseUrl.trim(),
                ttsVolcengineApiKey = ttsVolcengineApiKey.trim(),
                ttsVolcengineSpeaker = ttsVolcengineSpeaker.trim()
                    .ifBlank { "zh_female_vv_uranus_bigtts" },
                ttsVolcengineModel = ttsVolcengineModel.trim()
                    .ifBlank { "seed-tts-2.0-standard" },
                ttsVolcengineContext = ttsVolcengineContext.trim(),
                ttsVolcenginePitch = ttsVolcenginePitch.coerceIn(-12, 12),
                ttsVolcengineToneFidelity = ttsVolcengineToneFidelity,
                ttsMiniMaxModel = ttsMiniMaxModel,
                ttsMiniMaxBaseUrl = ttsMiniMaxBaseUrl.trim(),
                ttsMiniMaxApiKey = ttsMiniMaxApiKey.trim(),
                ttsMiniMaxVoice = ttsMiniMaxVoice.trim().ifBlank { "male-qn-qingse" },
                ttsMiniMaxEmotion = ttsMiniMaxEmotion.trim(),
                ttsMiniMaxSpeed = ttsMiniMaxSpeed.coerceIn(0.5f, 2.0f),
                ttsMiniMaxPitch = ttsMiniMaxPitch.coerceIn(-12, 12),
                ttsMimoModel = ttsMimoModel,
                ttsMimoBaseUrl = ttsMimoBaseUrl.trim(),
                ttsMimoApiKey = ttsMimoApiKey.trim(),
                ttsMimoVoice = ttsMimoVoice.trim().ifBlank { "mimo_default" },
                ttsMimoInstruction = ttsMimoInstruction.trim(),
                ttsMimoVoiceDesignPrompt = ttsMimoVoiceDesignPrompt.trim(),
                ttsMimoVoiceCloneInstruction = ttsMimoVoiceCloneInstruction.trim(),
                ttsMimoVoiceSampleUri = ttsMimoVoiceSampleUri.trim(),
                renderMode = renderMode,
                translationBlockInteractionMode = translationBlockInteractionMode,
                overlayPlacement = placement,
                overlayStyleMode = overlayStyleMode,
                overlayTheme = overlayTheme,
                customBgColor = customBg,
                customFgColor = customFg,
                customBorderColor = customBorder,
                customBorderWidth = customBorderW,
                overlayOffsetX = offsetX,
                overlayOffsetY = offsetY,
                ocrEngine = ocrEngine,
                autoOcr = autoOcr.normalized(),
                baiduOcrApiKey = baiduKey.trim(),
                baiduOcrSecretKey = baiduSecret.trim(),
                baiduOcrEndpoint = baiduEndpoint,
                baiduOcrLanguage = baiduLanguage,
                umiOcrBaseUrl = umiOcrBaseUrl.trim(),
                lunaOcrBaseUrl = lunaOcrBaseUrl.trim(),
                paddleAiStudioToken = paddleAiStudioToken.trim(),
                tencentSecretId = tencentId.trim(),
                tencentSecretKey = tencentKey.trim(),
                tencentRegion = tencentRegion.trim().ifBlank { "ap-guangzhou" },
                tencentOcrEndpoint = tencentEndpoint,
                tencentOcrLanguage = tencentLanguage,
                preprocess = preprocess,
                a11yVolumeTrigger = a11yVolume,
                floatingButtonSizeDp = floatingButtonSizeDp.coerceIn(32, 96),
                floatingButtonAlpha = normalizedFloatingButtonAlpha(floatingButtonAlpha),
                floatingButtonSnapToEdge = floatingButtonSnapToEdge,
                floatingButtonAutoDock = floatingButtonAutoDock,
                floatingButtonDockInsetDp = floatingButtonDockInsetDp.coerceIn(0, 40),
                overlayAllowWrap = allowWrap,
                overlayAvoidCollision = avoidCollision,
                apiTimeoutSeconds = apiTimeoutSeconds.coerceIn(5, 300),
                mergeAdjacentBlocks = mergeAdjacentBlocks,
                mergeStrength = mergeStrength,
                translationContextMode = translationContextMode,
                cleartextAllowedHosts = cleartextHostsWithLocalOcrUrls(
                    cleartextAllowedHosts,
                    umiOcrBaseUrl,
                    lunaOcrBaseUrl,
                    ttsHttpBaseUrl,
                    ttsMiniMaxBaseUrl,
                    ttsMimoBaseUrl,
                    ttsVolcengineBaseUrl,
                ),
                translatorEngine = translatorEngine,
                deeplApiKey = deeplKey.trim(),
                deeplPro = deeplPro,
                deeplProtocol = deeplProtocol,
                deeplBaseUrl = deeplBaseUrl.trim(),
                deeplBearerAuth = deeplBearerAuth,
                deeplCustomToken = deeplCustomToken.trim(),
                niuTransMode = niuTransMode,
                niuTransApiKey = niuTransApiKey.trim(),
                niuTransAppId = niuTransAppId.trim(),
                niuTransTermLibraryId = niuTransTermLibraryId.trim(),
                niuTransMemoryLibraryId = niuTransMemoryLibraryId.trim(),
                youdaoAppKey = youdaoAppKey.trim(),
                youdaoAppSecret = youdaoAppSecret.trim(),
                volcAccessKeyId = volcAccessKeyId.trim(),
                volcSecretAccessKey = volcSecretAccessKey.trim(),
                volcRegion = volcRegion.trim().ifBlank { "cn-north-1" },
                baiduFanyiAppId = baiduFanyiAppId.trim(),
                baiduFanyiSecretKey = baiduFanyiSecretKey.trim(),
                overlayFonts = overlayFonts,
                activeTranslationPresetId = activeTranslationPresetId,
            )
        }
    }

    suspend fun setActiveTranslationPreset(id: String) {
        repo.update { it.copy(activeTranslationPresetId = id) }
    }

    suspend fun savePaddleModelVersion(version: dev.clickn.translate.data.PaddleModelVersion) {
        repo.update { it.copy(paddleModelVersion = version) }
    }

    /** 悬浮窗口内容形态（原文+译文 / 仅译文）。立即落盘 + 即时生效，不走 [save] 流程。 */
    suspend fun saveFloatingWindowContentMode(mode: dev.clickn.translate.data.FloatingWindowContentMode) {
        repo.update { it.copy(floatingWindowContentMode = mode) }
    }

    /** 悬浮窗口锁定开关：锁定后禁用拖拽 / resize。 */
    suspend fun saveFloatingWindowLocked(locked: Boolean) {
        repo.update { it.copy(floatingWindowLocked = locked) }
    }

    /** CUSTOM 主题的边框样式（SOLID / DASHED / DOTTED / DOUBLE / GROOVE），立即生效。 */
    suspend fun saveCustomBorderStyle(style: dev.clickn.translate.data.BorderStyle) {
        repo.update { it.copy(customBorderStyle = style) }
    }

    suspend fun saveCaptureRegionBorderEnabled(enabled: Boolean) {
        repo.update { it.copy(captureRegionBorderEnabled = enabled) }
    }

    suspend fun saveCaptureRegionHideOnCapture(enabled: Boolean) {
        repo.update { it.copy(captureRegionHideOnCapture = enabled) }
    }

    suspend fun saveCaptureRegionBorderColor(color: Int) {
        repo.update { it.copy(captureRegionBorderColor = color) }
    }

    suspend fun saveCaptureRegionBorderWidth(widthDp: Int) {
        repo.update {
            it.copy(captureRegionBorderWidthDp = normalizedCaptureRegionBorderWidthDp(widthDp))
        }
    }

    suspend fun saveCaptureRegionBorderStyle(style: CaptureRegionBorderStyle) {
        repo.update { it.copy(captureRegionBorderStyle = style) }
    }

    suspend fun saveCaptureRegionAdjustmentEnabled(enabled: Boolean) {
        repo.update { it.copy(captureRegionAdjustmentEnabled = enabled) }
    }

    suspend fun saveWordSelectPreciseAdjust(enabled: Boolean) {
        repo.update { it.copy(wordSelectPreciseAdjust = enabled) }
    }

    suspend fun saveWordSelectCardMode(enabled: Boolean) {
        repo.update { it.copy(wordSelectCardMode = enabled) }
    }

    suspend fun saveWordSelectExtractOnly(enabled: Boolean) {
        repo.update { it.copy(wordSelectExtractOnly = enabled) }
    }

    suspend fun saveWordSelectRememberRegion(enabled: Boolean) {
        repo.update { it.copy(wordSelectRememberRegion = enabled) }
    }

    suspend fun saveFloatingWindowAutoHideWhenObstructing(enabled: Boolean) {
        repo.update { it.copy(floatingWindowAutoHideWhenObstructing = enabled) }
    }

    /** 弧菜单按钮顺序：拖拽完即时落盘 + 生效，不走主 [save] 流程的 dirty 判定。 */
    suspend fun saveArcMenuOrder(order: List<dev.clickn.translate.data.MenuItemId>) {
        repo.update { it.copy(floatingMenuItemOrder = FloatingMenu.normalizeOrder(order)) }
    }

    suspend fun saveArcMenuPageSize(size: Int) {
        repo.update { it.copy(arcMenuPageSize = FloatingMenu.coercePageSize(size)) }
    }

    suspend fun saveInputTranslationDoubleAction(action: InputTranslationDoubleAction) {
        repo.update { it.copy(inputTranslationDoubleAction = action) }
    }

    suspend fun createTranslationPresetFromCurrent(
        name: String,
        shortName: String
    ): TranslationPreset {
        val current = repo.get()
        val preset = TranslationPresetCatalog.fromSettings(
                id = "custom_${java.util.UUID.randomUUID()}",
                name = name.trim().ifBlank { "Custom preset" },
                shortName = shortName.trim().ifBlank { name.trim().take(8).ifBlank { "Custom" } },
                settings = current
            )
        return repo.saveTranslationPreset(preset, current)
    }

    suspend fun duplicateTranslationPreset(
        id: String,
        name: String,
        shortName: String
    ): TranslationPreset? {
        val source = TranslationPresetCatalog.find(repo.get().translationPresets, id) ?: return null
        return repo.duplicateTranslationPreset(
            id, name.trim().ifBlank { "${source.name} Copy" },
            shortName.trim().ifBlank { source.shortName },
        )
    }

    suspend fun saveTranslationPreset(preset: TranslationPreset, source: Settings): TranslationPreset =
        repo.saveTranslationPreset(preset, source)

    suspend fun deleteTranslationPreset(id: String) {
        if (TranslationPresetCatalog.isBuiltIn(id)) return
        repo.update { current ->
            current.copy(
                translationPresets = current.translationPresets.filterNot { it.id == id },
                activeTranslationPresetId = current.activeTranslationPresetId.takeIf { it != id }.orEmpty()
            )
        }
    }

    suspend fun importTranslationPresets(
        imported: List<TranslationPreset>
    ): TranslationPresetImportResult {
        var importResult: TranslationPresetImportResult? = null
        repo.updateAfterPresetImport(imported.mapTo(mutableSetOf()) { it.name }) { current ->
            val result = TranslationPresetTransfer.mergeImportedPresets(
                existing = current.translationPresets,
                imported = imported,
            )
            importResult = result
            val activeId = current.activeTranslationPresetId.takeIf { id ->
                id.isNotBlank() && TranslationPresetCatalog.find(result.presets, id) != null
            }.orEmpty()
            current.copy(
                translationPresets = result.presets,
                activeTranslationPresetId = activeId,
            )
        }
        return requireNotNull(importResult)
    }

    suspend fun applyTranslationPreset(id: String): Settings? = repo.applyTranslationPreset(id)

    suspend fun matchingCredentialPresetIds(source: Settings): Set<String> = repo.matchingCredentialPresetIds(source)

    /** 文本方向自动判别开关。立即落盘 + 即时生效，不走 [save] 流程的 dirty 判定。 */
    suspend fun saveTextOrientationAutoDetect(enabled: Boolean) {
        repo.update { it.copy(textOrientationAutoDetect = enabled) }
    }

    suspend fun saveCaptureContentOrientation(
        orientation: dev.clickn.translate.data.CaptureContentOrientation,
    ) {
        repo.update { it.copy(captureContentOrientation = orientation) }
    }

    /** 手动锁定文本方向（null = 解除锁定，走自动判别）。 */
    suspend fun saveManualTextOrientation(orient: dev.clickn.translate.ocr.TextOrientation?) {
        repo.update { it.copy(manualTextOrientation = orient) }
    }

    suspend fun saveTranslationOutputLayout(layout: dev.clickn.translate.data.TranslationOutputLayout) {
        repo.update { it.copy(translationOutputLayout = layout) }
    }

    suspend fun saveTranslationOutputFollowRecognition(enabled: Boolean) {
        repo.update { it.copy(translationOutputFollowRecognition = enabled) }
    }

    suspend fun saveTranslationOutputDirection(direction: dev.clickn.translate.data.TranslationOutputDirection) {
        repo.update { it.copy(translationOutputDirection = direction) }
    }

    suspend fun saveGlossarySettings(
        enabled: Boolean,
        detectionMode: dev.clickn.translate.data.ForegroundAppDetectionMode,
        sendAppName: Boolean,
    ) {
        repo.update {
            it.copy(
                translationGlossaryEnabled = enabled,
                foregroundAppDetectionMode = detectionMode,
                sendAppNameToTranslator = sendAppName,
            )
        }
    }

    /** 重置悬浮窗口位置 / 大小到默认（X=Y=-1 居中，W/H 回默认）。 */
    suspend fun resetFloatingWindowGeometry() {
        repo.update {
            it.copy(
                floatingWindowX = -1,
                floatingWindowY = -1,
                floatingWindowWidthDp = 320,
                floatingWindowHeightDp = 180
            )
        }
    }

    /**
     * 切换语言星标。已收藏则移除；未收藏则追加到末尾。立即落盘，绕过 SettingsScreen
     * 的 dirty 检测——星标是用户的小操作，不应该等"保存"按钮。
     */
    suspend fun togglePinLanguage(code: String) {
        repo.update { current ->
            val list = current.pinnedLanguages
            val next = if (list.contains(code)) list - code else list + code
            current.copy(pinnedLanguages = next)
        }
    }

    data class DownloadableModelUiState(
        val status: String,
        val ready: Boolean,
    )

    suspend fun paddleModelStatus(): String = paddleModelStatus(repo.get().paddleModelVersion)

    suspend fun paddleModelUiState(): DownloadableModelUiState =
        paddleModelUiState(repo.get().paddleModelVersion)

    fun paddleModelStatus(version: dev.clickn.translate.data.PaddleModelVersion): String {
        return paddleModelUiState(version).status
    }

    fun paddleModelUiState(version: dev.clickn.translate.data.PaddleModelVersion): DownloadableModelUiState {
        val readiness = modelReadinessChecker.paddle(version)
        return if (readiness.installed) {
            val total = readiness.totalBytes / 1024
            DownloadableModelUiState(
                status = appContext.getString(R.string.settings_paddle_status_ready_format, total.toInt()),
                ready = true,
            )
        } else {
            DownloadableModelUiState(
                status = appContext.getString(R.string.settings_paddle_status_missing_hint),
                ready = false,
            )
        }
    }

    suspend fun downloadPaddleModels(onProgress: (String) -> Unit) {
        downloadPaddleModels(repo.get().paddleModelVersion, onProgress)
    }

    suspend fun downloadPaddleModels(version: dev.clickn.translate.data.PaddleModelVersion, onProgress: (String) -> Unit) {
        downloadModels(listOf(ModelDownloadSpec.paddle(version)), onProgress)
    }

    fun deletePaddleModels() {
        paddleInstaller.deleteAll()
    }

    suspend fun importPaddleFromLocal(uris: List<android.net.Uri>): Int =
        importPaddleFromLocal(repo.get().paddleModelVersion, uris)

    suspend fun importPaddleFromLocal(
        version: dev.clickn.translate.data.PaddleModelVersion,
        uris: List<android.net.Uri>,
    ): Int = paddleInstaller.importFromLocal(uris, version)

    /** PaddleOCR 模型是否已就位；日漫 OCR 的依赖由后台下载管线统一处理。 */
    suspend fun isPaddleInstalled(): Boolean = isPaddleInstalled(repo.get().paddleModelVersion)

    fun isPaddleInstalled(version: dev.clickn.translate.data.PaddleModelVersion): Boolean =
        paddleModelUiState(version).ready

    // —— manga-ocr 端侧（日漫 OCR）——
    // 与 paddle 5 个方法严格对称。模型 ~160MB 比 paddle 大一个数量级，状态里用 MB 而非 KB。

    fun mangaOcrModelStatus(): String {
        return mangaOcrModelUiState().status
    }

    fun mangaOcrModelUiState(): DownloadableModelUiState {
        val readiness = modelReadinessChecker.mangaOcr()
        return if (readiness.installed) {
            val totalMb = readiness.totalBytes / (1024 * 1024)
            DownloadableModelUiState(
                status = appContext.getString(R.string.settings_manga_ocr_status_ready_format, totalMb.toInt()),
                ready = true,
            )
        } else {
            DownloadableModelUiState(
                status = appContext.getString(R.string.settings_manga_ocr_status_missing_hint),
                ready = false,
            )
        }
    }

    fun mangaOcrModelReady(): Boolean = mangaOcrModelUiState().ready

    suspend fun downloadMangaOcrModels(onProgress: (String) -> Unit) {
        downloadModels(listOf(ModelDownloadSpec.mangaOcr()), onProgress)
    }

    fun deleteMangaOcrModels() {
        mangaOcrInstaller.deleteAll()
    }

    suspend fun importMangaOcrFromLocal(uris: List<android.net.Uri>): Int =
        mangaOcrInstaller.importFromLocal(uris)

    // —— Paddle doc-orientation ONNX model ——

    fun orientationModelStatus(): String {
        return orientationModelUiState().status
    }

    fun orientationModelUiState(): DownloadableModelUiState {
        val readiness = modelReadinessChecker.orientation()
        return if (readiness.installed) {
            DownloadableModelUiState(
                status = appContext.getString(
                    R.string.settings_orientation_model_status_ready_format,
                    (readiness.totalBytes / 1024).toInt()
                ),
                ready = true,
            )
        } else {
            DownloadableModelUiState(
                status = appContext.getString(R.string.settings_orientation_model_status_missing_hint),
                ready = false,
            )
        }
    }

    fun orientationModelReady(): Boolean = orientationModelUiState().ready

    suspend fun downloadOrientationModel(onProgress: (String) -> Unit) {
        downloadModels(listOf(ModelDownloadSpec.orientation()), onProgress)
    }

    fun deleteOrientationModel() {
        orientationModelInstaller.deleteAll()
    }

    suspend fun importOrientationModelFromLocal(uris: List<android.net.Uri>): Int =
        orientationModelInstaller.importFromLocal(uris)

    // —— 端侧 LLM 翻译 ——

    fun llmDeviceCapable(): Boolean = modelReadinessChecker.isLocalLlmSupported()

    data class LlmModelUiState(
        val status: String,
        val ready: Boolean,
    )

    fun llmModelUiState(kind: LlmModelKind): LlmModelUiState {
        val readiness = modelReadinessChecker.llm(kind)
        return if (readiness.installed) {
            val mb = (readiness.totalBytes / 1024 / 1024).toInt()
            LlmModelUiState(
                status = appContext.getString(R.string.llm_status_ready, "${kind.displayName} $mb"),
                ready = true,
            )
        } else {
            LlmModelUiState(
                status = appContext.getString(R.string.llm_status_missing),
                ready = false,
            )
        }
    }

    fun llmStatus(kind: LlmModelKind): String = llmModelUiState(kind).status

    fun llmModelReady(kind: LlmModelKind): Boolean = llmModelUiState(kind).ready

    suspend fun downloadLlmModel(kind: LlmModelKind, onProgress: (String) -> Unit) {
        downloadModels(listOf(ModelDownloadSpec.llm(kind)), onProgress)
    }

    suspend fun downloadModels(
        specs: List<ModelDownloadSpec>,
        onProgress: (String) -> Unit,
        ownerPresetId: String? = null,
    ) {
        modelDownloadManager.enqueueAndAwait(specs, onProgress, ownerPresetId)
    }

    suspend fun downloadModelsIndependently(
        specs: List<ModelDownloadSpec>,
        onProgress: (String) -> Unit,
        ownerPresetId: String? = null,
    ) {
        modelDownloadManager.enqueueIndependentlyAndAwait(specs, onProgress, ownerPresetId)
    }

    fun cancelModelDownload(workId: java.util.UUID) = modelDownloadManager.cancel(workId)

    fun deleteLlmModel(kind: LlmModelKind): Boolean = llmInstaller.delete(kind)

    suspend fun saveLlmMirror(choice: dev.clickn.translate.data.LlmMirrorChoice, customUrl: String) {
        repo.update { it.copy(localLlmMirror = choice, localLlmMirrorUrl = customUrl.trim()) }
    }

    suspend fun savePaddleDetectionProfile(profile: dev.clickn.translate.data.PaddleDetectionProfile) {
        repo.update { it.copy(paddleDetectionProfile = profile) }
    }

    /** DBNet 阈值即时落盘；prob/score 共用，unclip 按 Paddle/MangaOCR 分开。 */
    suspend fun saveDbnetThresholds(
        ocrEngine: OcrEngineKind,
        prob: Float,
        score: Float,
        unclip: Float,
    ) {
        repo.update {
            val clampedUnclip = unclip.coerceIn(1.2f, 2.6f)
            it.copy(
                dbnetProbThresh = prob.coerceIn(0.05f, 0.5f),
                dbnetBoxScoreThresh = score.coerceIn(0.2f, 0.8f),
                dbnetUnclipRatio = if (ocrEngine == OcrEngineKind.MANGA_OCR_JA) {
                    it.dbnetUnclipRatio
                } else {
                    clampedUnclip
                },
                mangaOcrDbnetUnclipRatio = if (ocrEngine == OcrEngineKind.MANGA_OCR_JA) {
                    clampedUnclip
                } else {
                    it.mangaOcrDbnetUnclipRatio
                },
                bubbleClusterGap = MangaOcrAdvancedSettingsPolicy.BUBBLE_CLUSTER_GAP,
                mangaOcrCropPaddingPx = MangaOcrAdvancedSettingsPolicy.CROP_PADDING_PX,
            )
        }
    }

    suspend fun saveLocalLlmInferenceParams(contextSize: Int, maxNewTokens: Int) {
        repo.update {
            it.copy(
                localLlmContextSize = contextSize.coerceIn(512, 4096),
                localLlmMaxNewTokens = maxNewTokens.coerceIn(32, 512),
            )
        }
    }

    suspend fun importLlmFromLocal(
        uris: List<android.net.Uri>,
        defaultKind: LlmModelKind,
    ): Int = llmInstaller.importFromLocal(uris, defaultKind)

    /**
     * 测试当前 UI 上未保存的翻译引擎配置是否可用。基于已存档的 Settings，把用户在设置页
     * 改但未保存的几个字段（baseUrl/key/model/deeplKey/deeplPro/engine/timeout）覆盖进去，
     * 避免要求用户必须先点"保存"才能测。
     */
    suspend fun testTranslator(
        translatorEngine: TranslatorEngine,
        baseUrl: String,
        apiKey: String,
        model: String,
        anthropicBaseUrl: String,
        anthropicApiKey: String,
        anthropicModel: String,
        deeplKey: String,
        deeplPro: Boolean,
        deeplProtocol: dev.clickn.translate.data.DeeplProtocol,
        deeplBaseUrl: String,
        deeplBearerAuth: Boolean,
        deeplCustomToken: String,
        niuTransMode: dev.clickn.translate.data.NiuTransMode,
        niuTransApiKey: String,
        niuTransAppId: String,
        niuTransTermLibraryId: String,
        niuTransMemoryLibraryId: String,
        youdaoAppKey: String,
        youdaoAppSecret: String,
        apiTimeoutSeconds: Int,
        volcAccessKeyId: String = "",
        volcSecretAccessKey: String = "",
        volcRegion: String = "cn-north-1",
        baiduFanyiAppId: String = "",
        baiduFanyiSecretKey: String = "",
        tencentSecretId: String = "",
        tencentSecretKey: String = "",
        tencentRegion: String = ""
    ): TestResult {
        val base = repo.get()
        val temp = base.copy(
            translatorEngine = translatorEngine,
            baseUrl = baseUrl.trim(),
            apiKey = apiKey.trim(),
            model = model.trim(),
            anthropicBaseUrl = anthropicBaseUrl.trim(),
            anthropicApiKey = anthropicApiKey.trim(),
            anthropicModel = anthropicModel.trim(),
            deeplApiKey = deeplKey.trim(),
            deeplPro = deeplPro,
            deeplProtocol = deeplProtocol,
            deeplBaseUrl = deeplBaseUrl.trim(),
            deeplBearerAuth = deeplBearerAuth,
            deeplCustomToken = deeplCustomToken.trim(),
            niuTransMode = niuTransMode,
            niuTransApiKey = niuTransApiKey.trim(),
            niuTransAppId = niuTransAppId.trim(),
            niuTransTermLibraryId = niuTransTermLibraryId.trim(),
            niuTransMemoryLibraryId = niuTransMemoryLibraryId.trim(),
            youdaoAppKey = youdaoAppKey.trim(),
            youdaoAppSecret = youdaoAppSecret.trim(),
            volcAccessKeyId = volcAccessKeyId.trim().ifBlank { base.volcAccessKeyId },
            volcSecretAccessKey = volcSecretAccessKey.trim().ifBlank { base.volcSecretAccessKey },
            volcRegion = volcRegion.trim().ifBlank { base.volcRegion },
            baiduFanyiAppId = baiduFanyiAppId.trim().ifBlank { base.baiduFanyiAppId },
            baiduFanyiSecretKey = baiduFanyiSecretKey.trim().ifBlank { base.baiduFanyiSecretKey },
            tencentSecretId = tencentSecretId.trim().ifBlank { base.tencentSecretId },
            tencentSecretKey = tencentSecretKey.trim().ifBlank { base.tencentSecretKey },
            tencentRegion = tencentRegion.trim().ifBlank { base.tencentRegion },
            apiTimeoutSeconds = apiTimeoutSeconds.coerceIn(5, 300)
        )
        return connectionTester.test(temp)
    }
}

internal fun cleartextHostsWithLocalOcrUrls(
    hosts: List<String>,
    umiOcrBaseUrl: String,
    lunaOcrBaseUrl: String,
    ttsHttpBaseUrl: String = "",
    ttsMiniMaxBaseUrl: String = "",
    ttsMimoBaseUrl: String = "",
    ttsVolcengineBaseUrl: String = "",
): List<String> {
    val normalized = dev.clickn.translate.data.CleartextHostPolicy.normalize(hosts)
    val umiHost = umiOcrHttpHostOrNull(umiOcrBaseUrl)
    val lunaHost = lunaOcrHttpHostOrNull(lunaOcrBaseUrl)
    val ttsHost = ttsHttpHostOrNull(ttsHttpBaseUrl)
    val miniMaxTtsHost = ttsApiHttpHostOrNull(ttsMiniMaxBaseUrl)
    val mimoTtsHost = ttsApiHttpHostOrNull(ttsMimoBaseUrl)
    val volcengineTtsHost = ttsApiHttpHostOrNull(ttsVolcengineBaseUrl)
    return (normalized + listOfNotNull(
        umiHost,
        lunaHost,
        ttsHost,
        miniMaxTtsHost,
        mimoTtsHost,
        volcengineTtsHost,
    ))
        .distinctBy { it.lowercase() }
}
