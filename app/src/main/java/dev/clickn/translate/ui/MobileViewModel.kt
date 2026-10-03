package dev.clickn.translate.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.translate.RoutingTranslator
import dev.clickn.translate.translate.TranslatorConnectionTester
import dev.clickn.translate.translate.TestResult
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json

@Serializable
data class MobileHistoryEntry(
    val id: Long,
    val source: String,
    val translated: String,
    val from: String,
    val to: String,
    val provider: String,
)

data class MobileModelState(val checking: Boolean = true, val translationReady: Boolean? = null,
    val ocrReady: Boolean? = null, val downloadedLanguages: Set<String> = emptySet(),
    val llmReady: Set<dev.clickn.translate.llm.LlmModelKind> = emptySet())

data class MobileTranslationState(val busy: Boolean = false, val result: String = "", val error: String? = null)

@HiltViewModel
class MobileViewModel @Inject constructor(
    @ApplicationContext context: Context,
    private val repo: SettingsRepository,
    private val translator: RoutingTranslator,
    private val tester: TranslatorConnectionTester,
    private val models: dev.clickn.translate.download.ModelReadinessChecker,
    private val shizuku: dev.clickn.translate.shizuku.ShizukuManager,
) : ViewModel() {
    val settings = repo.settings.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    private val historyPrefs = context.getSharedPreferences("clickn_text_history", Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }
    private val serializer = ListSerializer(MobileHistoryEntry.serializer())
    private val _history = MutableStateFlow(runCatching {
        json.decodeFromString(serializer, historyPrefs.getString("entries", "[]")!!)
    }.getOrDefault(emptyList()))
    val history = _history.asStateFlow()
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
    private val _captureReady = MutableStateFlow<Boolean?>(null)
    val captureReady = _captureReady.asStateFlow()
    fun prepareShizuku() = viewModelScope.launch {
        _captureReady.value = null
        try {
            val ready = shizuku.ensureReady()
            if (ready) dev.clickn.translate.capture.CaptureStartPreference.select(dev.clickn.translate.capture.CaptureStartMode.SHIZUKU)
            _captureReady.value = ready
        } catch (cancelled: CancellationException) { throw cancelled }
        catch (_: Exception) { _captureReady.value = false }
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

    fun refreshModels(s: Settings) {
        val request = ++readinessRequest
        readinessJob?.cancel()
        _models.value = _models.value.copy(checking = true)
        readinessJob = viewModelScope.launch {
            try {
                val installed = runCatching { translator.getDownloadedMlKitLanguageModels() }.getOrDefault(emptySet())
                val state = kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                    val llm = dev.clickn.translate.llm.LlmModelKind.entries.filter { models.llm(it).ready }.toSet()
                    fun routeReady(route: dev.clickn.translate.data.AutoOcrRoute): Boolean = when (route.engine) {
                        dev.clickn.translate.data.OcrEngineKind.PADDLE_ONNX -> models.paddle(route.paddleVersion).ready
                        dev.clickn.translate.data.OcrEngineKind.MANGA_OCR_JA -> models.mangaOcr().ready
                        else -> dev.clickn.translate.data.AutoOcrRoutingPolicy.configured(s, route)
                    }
                    val ocrReady = if (s.ocrEngine == dev.clickn.translate.data.OcrEngineKind.ML_KIT_AUTO) {
                        s.sourceLang == "auto" || dev.clickn.translate.data.AutoOcrRoutingPolicy.resolve(s, s.sourceLang, ::routeReady) != null
                    } else routeReady(dev.clickn.translate.data.AutoOcrRoute(s.ocrEngine, s.paddleModelVersion)) &&
                        (s.sourceLang == "auto" || dev.clickn.translate.ocr.OcrLanguageCapability.supports(s, s.sourceLang))
                    val translated = when (s.translatorEngine) {
                        dev.clickn.translate.data.TranslatorEngine.GOOGLE_ML_KIT -> runCatching { translator.areMlKitLanguagePairModelsDownloaded(s.sourceLang, s.targetLang) }.getOrDefault(false)
                        dev.clickn.translate.data.TranslatorEngine.LOCAL_HY_MT2 -> dev.clickn.translate.llm.LlmModelKind.HY_MT2_1_8B_Q4_K_M in llm
                        dev.clickn.translate.data.TranslatorEngine.LOCAL_SAKURA -> dev.clickn.translate.llm.LlmModelKind.SAKURA_1_5B_Q4 in llm
                        else -> null
                    }
                    MobileModelState(false, translated, ocrReady, installed, llm)
                }
                if (request == readinessRequest) _models.value = state
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { if (request == readinessRequest) _models.value = MobileModelState(checking = false, translationReady = false, ocrReady = false) }
        }
    }
    fun downloadOfflinePair(s: Settings) {
        if (_offlineBusy.value) return
        offlineJob = viewModelScope.launch {
            _offlineBusy.value = true; _offlineError.value = false
            try {
                val pair = mobileMlKitPair(s)
                translator.downloadMlKitLanguagePair(pair.sourceLang, pair.targetLang, maxOf(120, s.timeoutSeconds))
                repo.update { it.copy(translatorEngine = pair.translatorEngine, sourceLang = pair.sourceLang, targetLang = pair.targetLang) }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { _offlineError.value = true }
            finally { _offlineBusy.value = false; refreshModels(repo.get()) }
        }
    }
    fun cancelOfflineDownload() { offlineJob?.cancel() }

    fun update(transform: (Settings) -> Settings) = viewModelScope.launch { repo.update(transform) }

    fun translate(source: String) {
        if (source.isBlank()) return
        val request = ++translationRequest
        translationJob?.cancel()
        translationJob = viewModelScope.launch {
            _translation.value = MobileTranslationState(busy = true)
            try {
                val snapshot = repo.get()
                val result = translator.translate(source, snapshot).orEmpty()
                if (request != translationRequest) return@launch
                check(result.isNotBlank()) { "Empty translation" }
                _translation.value = MobileTranslationState(result = result)
                val entry = MobileHistoryEntry(maxOf(System.currentTimeMillis(), (_history.value.firstOrNull()?.id ?: 0L) + 1L), source, result,
                    snapshot.sourceLang, snapshot.targetLang, snapshot.translatorEngine.name)
                _history.value = (listOf(entry) + _history.value.filterNot {
                    it.source == source && it.from == entry.from && it.to == entry.to && it.provider == entry.provider
                }).take(50)
                persistHistory()
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) {
                if (request == translationRequest) _translation.value = MobileTranslationState(error = error.javaClass.simpleName)
            } finally { if (request == translationRequest) _translation.value = _translation.value.copy(busy = false) }
        }
    }

    fun resetTranslation() { ++translationRequest; translationJob?.cancel(); _translation.value = MobileTranslationState() }
    fun clearHistory() { _history.value = emptyList(); persistHistory() }
    private fun persistHistory() { historyPrefs.edit().putString("entries", json.encodeToString(serializer, _history.value)).apply() }

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
