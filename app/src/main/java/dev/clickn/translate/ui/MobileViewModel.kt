package dev.clickn.translate.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.history.TextHistoryEntry
import dev.clickn.translate.history.TextHistoryIssue
import dev.clickn.translate.history.TextHistoryRepository
import dev.clickn.translate.history.TextHistoryState
import dev.clickn.translate.translate.RoutingTranslator
import dev.clickn.translate.translate.TranslatorConnectionTester
import dev.clickn.translate.translate.TestResult
import dev.clickn.translate.translate.TranslationFailureDescriptor
import dev.clickn.translate.translate.describeTranslationFailure
import dev.clickn.translate.shizuku.ShizukuCapabilities
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

data class MobileModelState(val checking: Boolean = true, val translationReady: Boolean? = null,
    val ocrReady: Boolean? = null, val downloadedLanguages: Set<String> = emptySet(),
    val llmReady: Set<dev.clickn.translate.llm.LlmModelKind> = emptySet(), val arabicOcrReady: Boolean = false)

data class MobileTranslationState(val busy: Boolean = false, val result: String = "", val error: TranslationFailureDescriptor? = null)

data class MobileShizukuState(
    val availability: ShizukuCapabilities.Availability = ShizukuCapabilities.Availability.NOT_INSTALLED,
    val checking: Boolean = true,
    val authorizing: Boolean = false,
    val authorizationDenied: Boolean = false,
)

@HiltViewModel
class MobileViewModel @Inject constructor(
    private val repo: SettingsRepository,
    private val historyRepository: TextHistoryRepository,
    private val translator: RoutingTranslator,
    private val tester: TranslatorConnectionTester,
    private val models: dev.clickn.translate.download.ModelReadinessChecker,
    private val shizuku: dev.clickn.translate.shizuku.ShizukuManager,
    private val tesseractModels: dev.clickn.translate.ocr.TesseractModelStore,
    private val modelDownloads: dev.clickn.translate.download.ModelDownloadManager,
    private val shizukuCapabilities: ShizukuCapabilities,
    @ApplicationContext private val appContext: Context,
) : ViewModel() {
    private val selectionSnapshots = repo.selectionSnapshots
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val settings = selectionSnapshots.map { it?.settings }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    private val _history = MutableStateFlow(TextHistoryState())
    val history = _history.asStateFlow()
    private var historyJob: Job? = null
    private val _translation = MutableStateFlow(MobileTranslationState())
    val translation = _translation.asStateFlow()
    private var translationJob: Job? = null
    private var translationRequest = 0L
    private val _connection = MutableStateFlow<TestResult?>(null)
    val connection = _connection.asStateFlow()
    private val _testing = MutableStateFlow(false)
    val testing = _testing.asStateFlow()
    private var testJob: Job? = null
    private var testRequest = 0L
    private val _shizukuState = MutableStateFlow(MobileShizukuState())
    val shizukuState = _shizukuState.asStateFlow()
    val captureModeInitialized = CaptureStartPreference.initialized
    private var shizukuRefreshJob: Job? = null
    private var shizukuRefreshRequest = 0L
    private var shizukuAuthorizationJob: Job? = null
    private var shizukuAuthorizationRequest = 0L

    suspend fun ensureCaptureModeInitialized() { CaptureStartPreference.initialize(appContext) }

    fun refreshShizuku() {
        val request = ++shizukuRefreshRequest
        shizukuRefreshJob?.cancel()
        _shizukuState.update { it.copy(checking = true) }
        shizukuRefreshJob = viewModelScope.launch {
            try {
                shizuku.verifyShellPrivilegeAsync()
                val availability = withContext(Dispatchers.IO) { shizukuCapabilities.availability(appContext) }
                if (request == shizukuRefreshRequest) _shizukuState.update {
                    it.copy(availability = availability, checking = false)
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) {
                if (request == shizukuRefreshRequest) _shizukuState.update {
                    it.copy(availability = ShizukuCapabilities.Availability.NOT_RUNNING, checking = false)
                }
            }
        }
    }

    fun prepareShizuku() {
        if (shizukuAuthorizationJob?.isActive == true) return
        val request = ++shizukuAuthorizationRequest
        val selectionRevision = CaptureStartPreference.revision()
        _shizukuState.update { it.copy(authorizing = true, authorizationDenied = false) }
        shizukuAuthorizationJob = viewModelScope.launch {
            try {
                ensureCaptureModeInitialized()
                val ready = withTimeoutOrNull(30_000) { shizuku.ensureReady() } == true
                currentCoroutineContext().ensureActive()
                if (request == shizukuAuthorizationRequest) {
                    val verified = ready && shizuku.isServiceRunning() && shizuku.hasPermission() && shizuku.shellPrivilegeOk.value
                    if (verified && CaptureStartPreference.selectIfUnchanged(CaptureStartMode.SHIZUKU, selectionRevision)) {
                        CaptureStartPreference.awaitPersistence()
                    }
                    if (request == shizukuAuthorizationRequest) _shizukuState.update { it.copy(authorizationDenied = !verified) }
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) {
                if (request == shizukuAuthorizationRequest) _shizukuState.update { it.copy(authorizationDenied = true) }
            } finally {
                if (request == shizukuAuthorizationRequest) {
                    _shizukuState.update { it.copy(authorizing = false) }
                    refreshShizuku()
                }
            }
        }
    }

    fun cancelShizukuPreparation() {
        ++shizukuAuthorizationRequest
        shizukuAuthorizationJob?.cancel()
        shizukuAuthorizationJob = null
        _shizukuState.update { it.copy(authorizing = false, authorizationDenied = false) }
    }

    fun selectSystemCapture() {
        cancelShizukuPreparation()
        CaptureStartPreference.select(CaptureStartMode.SYSTEM)
    }

    private val _models = MutableStateFlow(MobileModelState())
    val modelState = _models.asStateFlow()
    private var readinessJob: Job? = null
    private var readinessRequest = 0L
    private val _offlineBusy = MutableStateFlow(false)
    val offlineBusy = _offlineBusy.asStateFlow()
    private val _offlineError = MutableStateFlow(false)
    val offlineError = _offlineError.asStateFlow()
    private var offlineJob: Job? = null
    private var offlineSpec: dev.clickn.translate.download.ModelDownloadSpec? = null
    val tesseractModelState = tesseractModels.state
    val modelDownloadWorkInfos = modelDownloads.workInfos
    private var arabicOcrJob: Job? = null

    fun enableArabicOcr() {
        if (arabicOcrJob?.isActive == true) return
        arabicOcrJob = viewModelScope.launch {
            val version = dev.clickn.translate.data.PaddleModelVersion.V5_ARABIC
            try {
                val baseline = repo.get()
                if (!withContext(Dispatchers.IO) { models.paddle(version).ready }) {
                    modelDownloads.enqueueAndAwait(listOf(dev.clickn.translate.download.ModelDownloadSpec.paddle(version)), {})
                }
                if (!withContext(Dispatchers.IO) { models.paddle(version).ready }) return@launch
                repo.update { current ->
                    // A later explicit OCR choice must survive this background download.
                    if (current.ocrEngine == baseline.ocrEngine && current.paddleModelVersion == baseline.paddleModelVersion) {
                        current.copy(ocrEngine = dev.clickn.translate.data.OcrEngineKind.PADDLE_ONNX, paddleModelVersion = version)
                    } else current
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { /* The shared download queue displays failures and retry. */ }
            finally { settings.value?.let(::refreshModels) }
        }
    }

    fun cancelArabicOcrDownload() {
        arabicOcrJob?.cancel()
        modelDownloads.cancel(dev.clickn.translate.download.ModelDownloadSpec.paddle(dev.clickn.translate.data.PaddleModelVersion.V5_ARABIC))
    }

    fun downloadTesseractModels() = viewModelScope.launch {
        try { modelDownloads.enqueueAndAwait(listOf(dev.clickn.translate.download.ModelDownloadSpec.tesseractArabic()), {}) }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { /* Queue/store state is displayed by the package hub. */ }
        finally { settings.value?.let(::refreshModels) }
    }
    fun cancelTesseractModels() = modelDownloads.cancel(dev.clickn.translate.download.ModelDownloadSpec.tesseractArabic())
    fun deleteTesseractModels() = viewModelScope.launch {
        tesseractModels.delete()
        settings.value?.let(::refreshModels)
    }

    init {
        reloadHistory()
        viewModelScope.launch { ensureCaptureModeInitialized() }
        viewModelScope.launch {
            combine(shizuku.binderAlive, shizuku.shellPrivilegeOk) { alive, privileged -> alive to privileged }
                .distinctUntilChanged().collect { (alive, privileged) ->
                    if (!alive || !privileged) _shizukuState.update {
                        it.copy(availability = if (alive) ShizukuCapabilities.Availability.INSTALLED_NOT_PAIRED
                            else ShizukuCapabilities.Availability.NOT_RUNNING, checking = true)
                    }
                    refreshShizuku()
                }
        }
        viewModelScope.launch {
            tesseractModels.state.map { it.ready }.distinctUntilChanged().drop(1).collect {
                settings.value?.let(::refreshModels)
            }
        }
    }

    fun refreshModels(s: Settings) {
        val request = ++readinessRequest
        readinessJob?.cancel()
        _models.value = _models.value.copy(checking = true)
        readinessJob = viewModelScope.launch {
            try {
                val installed = runCatching { translator.getDownloadedMlKitLanguageModels() }.getOrDefault(emptySet())
                val state = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                    tesseractModels.refresh()
                    val arabicPaddleReady = models.paddle(dev.clickn.translate.data.PaddleModelVersion.V5_ARABIC).ready
                    val llm = dev.clickn.translate.llm.LlmModelKind.entries.filter { models.llm(it).ready }.toSet()
                    fun routeReady(route: dev.clickn.translate.data.AutoOcrRoute): Boolean = when (route.engine) {
                        dev.clickn.translate.data.OcrEngineKind.PADDLE_ONNX -> models.paddle(route.paddleVersion).ready
                        dev.clickn.translate.data.OcrEngineKind.MANGA_OCR_JA -> models.mangaOcr().ready
                        dev.clickn.translate.data.OcrEngineKind.TESSERACT_ARABIC -> tesseractModels.state.value.ready
                        else -> dev.clickn.translate.data.AutoOcrRoutingPolicy.configured(s, route)
                    }
                    val ocrReady = if (s.ocrEngine == dev.clickn.translate.data.OcrEngineKind.ML_KIT_AUTO) {
                        if (dev.clickn.translate.ocr.requiresArabicOcrBootstrap(s) && !tesseractModels.state.value.ready && !arabicPaddleReady) false
                        else s.sourceLang == "auto" || dev.clickn.translate.data.AutoOcrRoutingPolicy.resolve(s, s.sourceLang, ::routeReady) != null
                    } else routeReady(dev.clickn.translate.data.AutoOcrRoute(s.ocrEngine, s.paddleModelVersion)) &&
                        (s.sourceLang == "auto" || dev.clickn.translate.ocr.OcrLanguageCapability.supports(s, s.sourceLang))
                    val translated = when (s.translatorEngine) {
                        dev.clickn.translate.data.TranslatorEngine.GOOGLE_ML_KIT -> runCatching { translator.areMlKitLanguagePairModelsDownloaded(s.sourceLang, s.targetLang) }.getOrDefault(false)
                        dev.clickn.translate.data.TranslatorEngine.LOCAL_HY_MT2 -> dev.clickn.translate.llm.LlmModelKind.HY_MT2_1_8B_Q4_K_M in llm
                        dev.clickn.translate.data.TranslatorEngine.LOCAL_SAKURA -> dev.clickn.translate.llm.LlmModelKind.SAKURA_1_5B_Q4 in llm
                        else -> null
                    }
                    MobileModelState(false, translated, ocrReady, installed, llm, arabicPaddleReady)
                }
                if (request == readinessRequest) _models.value = state
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { if (request == readinessRequest) _models.value = MobileModelState(checking = false, translationReady = false, ocrReady = false) }
        }
    }
    fun downloadOfflinePair(s: Settings) {
        val baseline = selectionSnapshots.value ?: return
        if (!_offlineBusy.compareAndSet(false, true)) return
        _offlineError.value = false
        offlineJob = viewModelScope.launch {
            try {
                val pair = mobileMlKitPair(s)
                val spec = dev.clickn.translate.download.ModelDownloadSpec.mlKitTranslation(pair.sourceLang, pair.targetLang)
                offlineSpec = spec
                OfflineTranslationActivationPolicy.downloadAndActivate(
                    baseline = baseline,
                    requestedPair = pair,
                    alreadyInstalled = { translator.areMlKitLanguagePairModelsDownloaded(pair.sourceLang, pair.targetLang) },
                    download = { modelDownloads.enqueueAndAwait(listOf(spec), {}) },
                    activate = repo::updateTranslationSelectionIfUnchanged,
                )
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { _offlineError.value = true }
            finally { offlineSpec = null; _offlineBusy.value = false; settings.value?.let(::refreshModels) }
        }
    }
    fun cancelOfflineDownload() { offlineSpec?.let(modelDownloads::cancel); offlineJob?.cancel() }

    fun cancelOfflineDownload(work: androidx.work.WorkInfo) {
        modelDownloads.cancel(work.id)
        if (offlineSpec?.let { dev.clickn.translate.download.ModelDownloadWorkPolicy.specTag(it) in work.tags } == true) {
            offlineJob?.cancel()
        }
    }

    fun update(transform: (Settings) -> Settings) = viewModelScope.launch { repo.update(transform) }

    fun selectTranslation(transform: (Settings) -> Settings) = viewModelScope.launch { repo.selectTranslation(transform) }

    private val providerSaves = ProviderSaveCoordinator(viewModelScope)
    internal val providerSaveState = providerSaves.status
    private val _providerEditor = MutableStateFlow<ProviderEditSession?>(null)
    internal val providerEditor = _providerEditor.asStateFlow()

    internal fun openProvider(current: Settings, engine: TranslatorEngine) {
        providerSaves.clearFailure()
        clearConnection()
        val initial = if (engine == TranslatorEngine.GOOGLE_ML_KIT) mobileMlKitPair(current)
            else current.copy(translatorEngine = engine)
        _providerEditor.value = ProviderEditSession(initial)
    }

    internal fun closeProvider() {
        _providerEditor.value = null
        clearConnection()
    }

    internal fun saveProvider(transform: (Settings) -> Settings) = providerSaves.save {
        repo.selectTranslation(transform)
        resetTranslation()
    }

    fun translate(source: String) {
        if (source.isBlank()) return
        val request = ++translationRequest
        translationJob?.cancel()
        translationJob = viewModelScope.launch {
            _translation.value = MobileTranslationState(busy = true)
            try {
                val snapshot = repo.get()
                val historyGeneration = try {
                    historyRepository.writeGeneration()
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (_: Exception) { historyUnavailable(); null }
                val result = translator.translate(source, snapshot).orEmpty()
                if (request != translationRequest) return@launch
                check(result.isNotBlank()) { "Empty translation" }
                if (historyGeneration != null) {
                    try {
                        historyRepository.save(TextHistoryEntry(createdAtMs = System.currentTimeMillis(),
                            source = source, translated = result, from = snapshot.sourceLang,
                            to = snapshot.targetLang, provider = snapshot.translatorEngine.name), historyGeneration)
                    } catch (cancelled: CancellationException) { throw cancelled }
                    catch (_: Exception) { historyUnavailable() }
                }
                if (request == translationRequest) _translation.value = MobileTranslationState(result = result)
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) {
                if (request == translationRequest) _translation.value = MobileTranslationState(error = describeTranslationFailure(error))
            } finally { if (request == translationRequest) _translation.value = _translation.value.copy(busy = false) }
        }
    }

    fun resetTranslation() { ++translationRequest; translationJob?.cancel(); _translation.value = MobileTranslationState() }
    fun clearHistory() = viewModelScope.launch {
        try { historyRepository.clear() }
        catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { historyUnavailable() }
    }

    fun reloadHistory() {
        historyJob?.cancel()
        _history.update { it.copy(loading = true, issue = null) }
        historyJob = viewModelScope.launch {
            try { historyRepository.observe().collect { _history.value = it } }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { historyUnavailable() }
        }
    }

    private fun historyUnavailable() {
        _history.update { it.copy(loading = false, issue = TextHistoryIssue.STORAGE) }
    }

    fun test(settings: Settings) {
        val request = ++testRequest
        testJob?.cancel()
        testJob = viewModelScope.launch {
            _testing.value = true
            _connection.value = null
            try {
                val result = tester.test(settings)
                // The UI never needs a server response body or a credential-bearing URL.
                if (request == testRequest) _connection.value = result.copy(message = if (result.success) "OK" else "Service unavailable")
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) { if (request == testRequest) _connection.value = TestResult(false, error.javaClass.simpleName) }
            finally { if (request == testRequest) _testing.value = false }
        }
    }
    fun clearConnection() { ++testRequest; testJob?.cancel(); _testing.value = false; _connection.value = null }
}
