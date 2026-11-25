// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.DialogInterface
import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.TextUtils
import android.view.View
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewModelScope
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.LogRepository
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.overlay.TranslationCardOverlay
import dev.clickn.translate.overlay.TtsPlaybackAction
import dev.clickn.translate.tts.TtsEngine
import dev.clickn.translate.tts.ttsFailureMessage
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import timber.log.Timber

/**
 * 系统「文字选中」菜单入口：用户在任意 App 长按选中文字 → 系统弹处理菜单 → 「Click'n'Translate翻译」
 * 出现其中（注册了 ACTION_PROCESS_TEXT）。点击后系统启动本 Activity 并把选中的文字
 * 放在 [Intent.EXTRA_PROCESS_TEXT]。
 *
 * Editable selections use an Activity-owned review and return only after explicit Replace.
 * Read-only selections retain the original overlay when allowed; otherwise review needs no SAW.
 */
@AndroidEntryPoint
class ProcessTextTranslateActivity : ComponentActivity() {
    override fun attachBaseContext(newBase: android.content.Context) {
        super.attachBaseContext(dev.clickn.translate.data.AppLocalePrefs.wrap(newBase))
    }

    @Inject lateinit var translator: Translator
    @Inject lateinit var settingsRepository: SettingsRepository
    @Inject lateinit var logRepository: LogRepository
    @Inject lateinit var ttsEngine: TtsEngine

    private val reviewModel: ProcessTextReviewViewModel by viewModels {
        ProcessTextReviewFactory(applicationContext, translator, settingsRepository, logRepository)
    }
    private var reviewing = false
    private var reviewDialog: AlertDialog? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setResult(Activity.RESULT_CANCELED)

        val text = when (intent.action) {
            Intent.ACTION_PROCESS_TEXT -> intent.getCharSequenceExtra(Intent.EXTRA_PROCESS_TEXT)
            Intent.ACTION_SEND -> if (intent.type == "text/plain") intent.getCharSequenceExtra(Intent.EXTRA_TEXT) else null
            else -> null
        }?.toString().orEmpty()
        if (text.isBlank()) {
            finish(); return
        }
        if (text.length > PROCESS_TEXT_MAX_LENGTH) {
            Toast.makeText(this, getString(R.string.process_text_too_long, PROCESS_TEXT_MAX_LENGTH), Toast.LENGTH_LONG).show()
            finish(); return
        }
        val readOnly = intent.action != Intent.ACTION_PROCESS_TEXT ||
            intent.getBooleanExtra(Intent.EXTRA_PROCESS_TEXT_READONLY, true)
        if (!readOnly || !Settings.canDrawOverlays(this)) {
            showReview(text, readOnly, savedInstanceState?.getBoolean(REVIEW_STARTED) != true)
            return
        }
        startReadOnlyOverlay(text)
        finish()
    }

    private fun showReview(text: String, readOnly: Boolean, translateNow: Boolean) {
        reviewing = true
        reviewModel.session.start(text, readOnly, translateNow)
        val density = resources.displayMetrics.density
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding((24 * density).toInt(), (8 * density).toInt(), (24 * density).toInt(), (8 * density).toInt())
        }
        fun label(resource: Int) = TextView(this).apply {
            setText(resource)
            setPadding(0, (12 * density).toInt(), 0, (4 * density).toInt())
            setTypeface(typeface, android.graphics.Typeface.BOLD)
        }
        body.addView(label(R.string.word_card_section_source))
        body.addView(TextView(this).apply {
            this.text = text
            textSize = 16f
            maxLines = 6
            ellipsize = TextUtils.TruncateAt.END
            setTextIsSelectable(true)
            textDirection = View.TEXT_DIRECTION_FIRST_STRONG
        })
        body.addView(label(R.string.word_card_section_translation))
        val progress = ProgressBar(this).apply { isIndeterminate = true }
        body.addView(progress)
        val translation = TextView(this).apply {
            textSize = 18f
            setTextIsSelectable(true)
            textDirection = View.TEXT_DIRECTION_FIRST_STRONG
        }
        body.addView(translation)
        val dialog = MaterialAlertDialogBuilder(this)
            .setTitle(R.string.process_text_label)
            .setView(ScrollView(this).apply { addView(body) })
            .setNegativeButton(if (readOnly) R.string.word_card_dismiss else android.R.string.cancel) { _, _ -> finishReview() }
            .setPositiveButton(if (readOnly) R.string.word_card_btn_copy_translation else R.string.process_text_replace, null)
            .apply { if (!readOnly) setNeutralButton(R.string.word_card_btn_copy_translation, null) }
            .create()
        reviewDialog = dialog
        fun render(state: ProcessTextReviewState?) {
            if (state == null || state.closed) return
            progress.visibility = if (state.busy) View.VISIBLE else View.GONE
            translation.text = when {
                state.busy -> getString(R.string.process_text_translating)
                state.interrupted -> getString(R.string.process_text_interrupted)
                state.failed -> getString(R.string.process_text_translate_failed)
                else -> state.translation
            }
            dialog.getButton(DialogInterface.BUTTON_POSITIVE)?.apply {
                setText(when {
                    state.failed || state.interrupted -> R.string.process_text_retry
                    readOnly -> R.string.word_card_btn_copy_translation
                    else -> R.string.process_text_replace
                })
                isEnabled = !state.busy && (state.failed || state.interrupted || state.succeeded)
            }
            dialog.getButton(DialogInterface.BUTTON_NEUTRAL)?.isEnabled = state.succeeded && !state.busy
        }
        dialog.setOnShowListener {
            dialog.getButton(DialogInterface.BUTTON_POSITIVE).setOnClickListener {
                val state = reviewModel.session.state.value ?: return@setOnClickListener
                when {
                    state.failed || state.interrupted -> reviewModel.session.retry()
                    readOnly -> copyReviewTranslation()
                    else -> reviewModel.session.replacement()?.let { replacement ->
                        setResult(Activity.RESULT_OK, Intent().putExtra(Intent.EXTRA_PROCESS_TEXT, replacement))
                        finishReview()
                    }
                }
            }
            dialog.getButton(DialogInterface.BUTTON_NEUTRAL)?.setOnClickListener { copyReviewTranslation() }
            render(reviewModel.session.state.value)
        }
        dialog.setOnCancelListener { finishReview() }
        dialog.show()
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                reviewModel.session.state.collect(::render)
            }
        }
    }

    private fun copyReviewTranslation() {
        val translated = reviewModel.session.copyText() ?: return
        try {
            (getSystemService(CLIPBOARD_SERVICE) as ClipboardManager)
                .setPrimaryClip(ClipData.newPlainText(getString(R.string.process_text_label), translated))
            Toast.makeText(this, R.string.word_card_btn_copied, Toast.LENGTH_SHORT).show()
            finishReview()
        } catch (_: Exception) {
            Toast.makeText(this, R.string.process_text_copy_failed, Toast.LENGTH_LONG).show()
        }
    }

    private fun finishReview() {
        reviewModel.session.close()
        finish()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        if (reviewing) outState.putBoolean(REVIEW_STARTED, true)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        reviewDialog?.setOnCancelListener(null)
        reviewDialog?.dismiss()
        reviewDialog = null
        if (reviewing && isFinishing) reviewModel.session.close()
        super.onDestroy()
    }

    private fun startReadOnlyOverlay(text: String) {

        // 翻译跑在 application scope；finish() 后 Activity 不在了也不影响协程。
        val app = dev.clickn.translate.data.AppLocalePrefs.live(applicationContext)
        val appScope = (application as ClickTranslateApp).appScope
        val translatingLabel = getString(R.string.process_text_translating)
        val failedLabel = getString(R.string.process_text_translate_failed)
        val engineFailedFmt = getString(R.string.log_msg_translate_failed_format)
        val operation = Job(appScope.coroutineContext[Job])
        appScope.launch(operation) {
            var ownedCard: TranslationCardOverlay? = null
            try {
            val settings = settingsRepository.get()
            val speechEngine = ttsEngine
            val speechLogRepository = logRepository
            val playbackSessionId = "process-text:${System.nanoTime()}"
            fun speechAction(
                role: ProcessTextSpeechRole,
                playbackKey: String = role.name.lowercase(),
            ): TtsPlaybackAction? {
                if (!settings.ttsEnabled) return null
                val playbackId = "$playbackSessionId:$playbackKey"
                fun dispatch(spokenText: String, toggle: Boolean) {
                    appScope.launch(Dispatchers.Main.immediate) {
                        runCatching {
                            val spokenSettings = processTextSpeechSettings(settings, role)
                            if (role == ProcessTextSpeechRole.SOURCE) {
                                if (toggle) speechEngine.toggleSource(spokenText, spokenSettings, playbackId)
                                else speechEngine.speakSource(spokenText, spokenSettings, playbackId)
                            } else if (toggle) {
                                speechEngine.toggle(spokenText, spokenSettings, playbackId)
                            } else {
                                speechEngine.speak(spokenText, spokenSettings, playbackId)
                            }
                        }.onFailure { error ->
                            if (error is CancellationException) throw error
                            Timber.w(error, "PROCESS_TEXT %s TTS failed", role.name.lowercase())
                            speechLogRepository.warn(
                                LogRepository.Category.TRANSLATE,
                                ttsFailureMessage(error),
                            )
                            Toast.makeText(
                                app,
                                app.ttsFailureMessage(error),
                                Toast.LENGTH_LONG,
                            ).show()
                        }
                    }
                }
                return TtsPlaybackAction(
                    playbackId = playbackId,
                    playbackState = speechEngine.playbackState,
                    onToggle = { spokenText -> dispatch(spokenText, true) },
                    onStart = { spokenText -> dispatch(spokenText, false) },
                )
            }
            val sourceSpeech = speechAction(ProcessTextSpeechRole.SOURCE)
            val translationSpeech = speechAction(ProcessTextSpeechRole.TRANSLATION)
            val dictionarySpeech = speechAction(
                role = ProcessTextSpeechRole.TRANSLATION,
                playbackKey = "dictionary",
            )
            // 浮卡用 applicationContext 避免持 Activity 引用 leak
            var renderingCard = false
            val onDismissed = { speechEngine.stop() }
            val card = TranslationCardOverlay(
                context = app,
                onDismissed = {
                    onDismissed()
                    if (!renderingCard) operation.cancel()
                },
            )
            ownedCard = card
            withContext(Dispatchers.Main) {
                renderingCard = true
                try { card.show(
                    sourceText = text,
                    translation = translatingLabel,
                    loading = true,
                    wordResult = null,
                    settings = settings,
                    onSpeakSource = sourceSpeech,
                ) } finally { renderingCard = false }
                if (!card.isShown()) {
                    Toast.makeText(app, failedLabel, Toast.LENGTH_LONG).show()
                    operation.cancel()
                }
            }
            val translateStartedAt = System.currentTimeMillis()
            val dictionaryTerm = WordHeuristic.manuallySelectedDictionaryTermOrNull(
                text = text,
                sourceLang = settings.sourceLang,
                translatorEngine = settings.translatorEngine,
            )
            Timber.i(
                "PROCESS_TEXT dictionary engine=%s sourceLang=%s selectedLength=%d eligible=%s termLength=%d",
                settings.translatorEngine.name,
                settings.sourceLang,
                text.length,
                dictionaryTerm != null,
                dictionaryTerm?.length ?: 0,
            )
            val outcome = WordSelectTranslationCoordinator(translator).execute(
                source = text,
                settings = settings,
                dictionaryTerm = dictionaryTerm,
                onPartialTranslation = { partial ->
                    withContext(Dispatchers.Main) { card.updateTranslation(partial) }
                },
                onWordResult = { result ->
                    withContext(Dispatchers.Main) { card.updateWordResult(result) }
                },
            )
            currentCoroutineContext().ensureActive()
            outcome.dictionaryError?.let { error ->
                Timber.w(error, "PROCESS_TEXT dictionary request failed")
                logRepository.warn(
                    LogRepository.Category.TRANSLATE,
                    "Dictionary lookup failed: ${error.javaClass.simpleName}: " +
                        error.message.orEmpty().take(160),
                )
            }
            outcome.translationError?.let { error ->
                Timber.w(error, "PROCESS_TEXT translate failed")
                logRepository.error(
                    LogRepository.Category.TRANSLATE,
                    String.format(engineFailedFmt, settings.translatorEngine.name),
                    error,
                    elapsedMs = elapsedSince(translateStartedAt),
                )
            }
            val presentation = processTextTranslationPresentation(outcome, failedLabel)
            Timber.i(
                "PROCESS_TEXT dictionary parsed=%s phonetic=%s pos=%d definitions=%d notes=%d examples=%d",
                outcome.wordResult != null,
                outcome.wordResult?.phonetic?.isNotBlank() == true,
                outcome.wordResult?.effectivePartsOfSpeech()?.size ?: 0,
                outcome.wordResult?.effectiveDefinitions()?.size ?: 0,
                outcome.wordResult?.difficultyNotes?.size ?: 0,
                outcome.wordResult?.examples?.size ?: 0,
            )
            if (!presentation.translationSucceeded && outcome.translationError == null) {
                logRepository.error(
                    LogRepository.Category.TRANSLATE,
                    String.format(engineFailedFmt, settings.translatorEngine.name),
                    elapsedMs = elapsedSince(translateStartedAt),
                )
            }
            if (presentation.translationSucceeded) {
                logRepository.pair(
                    LogRepository.Category.TRANSLATE,
                    text,
                    presentation.translation,
                    elapsedMs = elapsedSince(translateStartedAt),
                )
            }
            withContext(Dispatchers.Main) {
                if (!card.isShown()) return@withContext
                renderingCard = true
                try { card.show(
                    sourceText = text,
                    translation = presentation.translation,
                    wordResult = outcome.wordResult,
                    settings = settings,
                    onSpeakSource = sourceSpeech,
                    onSpeakTranslation = translationSpeech.takeIf {
                        presentation.translationSucceeded
                    },
                    onSpeakDictionary = dictionarySpeech.takeIf { outcome.wordResult != null },
                ) } finally { renderingCard = false }
            }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                Timber.w(error, "PROCESS_TEXT presentation failed")
                withContext(Dispatchers.Main) {
                    ownedCard?.dismiss()
                    Toast.makeText(app, failedLabel, Toast.LENGTH_LONG).show()
                }
            } finally { operation.complete() }
        }
    }

    private companion object { const val REVIEW_STARTED = "process-text-review-started" }

    private fun elapsedSince(startMs: Long): Long =
        (System.currentTimeMillis() - startMs).coerceAtLeast(0L)
}

internal enum class ProcessTextSpeechRole {
    SOURCE,
    TRANSLATION,
}

internal data class ProcessTextTranslationPresentation(
    val translation: String,
    val translationSucceeded: Boolean,
)

internal fun processTextTranslationPresentation(
    outcome: WordSelectTranslationOutcome,
    failureText: String,
): ProcessTextTranslationPresentation {
    val dictionaryFallback = outcome.wordResult?.fallbackTranslation
        ?: outcome.wordResult?.effectiveDefinitions()?.firstOrNull()
    val translation = outcome.translation?.takeIf(String::isNotBlank)
        ?: dictionaryFallback?.takeIf(String::isNotBlank)
    return ProcessTextTranslationPresentation(
        translation = translation ?: failureText,
        translationSucceeded = translation != null,
    )
}

internal fun processTextSpeechSettings(
    settings: dev.clickn.translate.data.Settings,
    role: ProcessTextSpeechRole,
): dev.clickn.translate.data.Settings = settings.copy(
    targetLang = when (role) {
        ProcessTextSpeechRole.SOURCE -> settings.sourceLang
        ProcessTextSpeechRole.TRANSLATION -> settings.targetLang
    },
)

internal const val PROCESS_TEXT_MAX_LENGTH = 20_000

internal data class ProcessTextReviewState(
    val source: String,
    val readOnly: Boolean,
    val busy: Boolean = false,
    val translation: String = "",
    val succeeded: Boolean = false,
    val failed: Boolean = false,
    val interrupted: Boolean = false,
    val closed: Boolean = false,
)

/** One user-owned request survives view recreation; closure revokes even a late backend result. */
internal class ProcessTextReviewSession(
    private val scope: CoroutineScope,
    private val translate: suspend (String) -> ProcessTextTranslationPresentation,
) {
    private val mutableState = MutableStateFlow<ProcessTextReviewState?>(null)
    val state = mutableState.asStateFlow()
    private var job: Job? = null
    private var closed = false

    fun start(source: String, readOnly: Boolean, translateNow: Boolean = true) {
        if (closed || mutableState.value != null) return
        require(source.isNotBlank() && source.length <= PROCESS_TEXT_MAX_LENGTH)
        mutableState.value = ProcessTextReviewState(source, readOnly, interrupted = !translateNow)
        if (translateNow) request()
    }

    fun retry() {
        val current = mutableState.value ?: return
        if (current.closed || current.busy || (!current.failed && !current.interrupted)) return
        request()
    }

    private fun request() {
        val current = mutableState.value ?: return
        if (current.closed) return
        mutableState.value = current.copy(busy = true, translation = "", succeeded = false,
            failed = false, interrupted = false)
        lateinit var admitted: Job
        admitted = scope.launch(start = CoroutineStart.LAZY) {
            try {
                val result = translate(current.source)
                currentCoroutineContext().ensureActive()
                if (job === admitted && mutableState.value?.closed == false) {
                    val success = result.translationSucceeded && result.translation.isNotBlank()
                    mutableState.value = current.copy(translation = if (success) result.translation else "",
                        succeeded = success, failed = !success, interrupted = false)
                }
            } catch (cancelled: CancellationException) {
                // Real owner cancellation remains cancellation. An independently interrupted backend
                // leaves an explicit Retry state rather than a permanent loading indicator.
                currentCoroutineContext().ensureActive()
                if (job === admitted && mutableState.value?.closed == false) {
                    mutableState.value = current.copy(interrupted = true)
                }
                throw cancelled
            } catch (_: Exception) {
                currentCoroutineContext().ensureActive()
                if (job === admitted && mutableState.value?.closed == false) {
                    mutableState.value = current.copy(failed = true, interrupted = false)
                }
            }
        }
        job = admitted
        admitted.start()
    }

    fun copyText(): String? = mutableState.value?.takeIf {
        !it.closed && !it.busy && it.succeeded
    }?.translation

    fun replacement(): String? = mutableState.value?.takeUnless { it.readOnly }?.let { copyText() }

    fun close() {
        closed = true
        mutableState.value = mutableState.value?.copy(busy = false, closed = true)
        job?.cancel()
    }
}

internal class ProcessTextReviewViewModel(
    translate: suspend (String) -> ProcessTextTranslationPresentation,
) : ViewModel() {
    val session = ProcessTextReviewSession(viewModelScope, translate)
    override fun onCleared() { session.close() }
}

private class ProcessTextReviewFactory(
    context: android.content.Context,
    private val translator: Translator,
    private val repository: SettingsRepository,
    private val logs: LogRepository,
) : ViewModelProvider.Factory {
    private val app = dev.clickn.translate.data.AppLocalePrefs.live(context.applicationContext)

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass == ProcessTextReviewViewModel::class.java)
        return ProcessTextReviewViewModel { source ->
            withContext(Dispatchers.IO) {
                val settings = repository.get()
                val started = System.currentTimeMillis()
                val outcome = WordSelectTranslationCoordinator(translator).execute(
                    source = source, settings = settings,
                    dictionaryTerm = WordHeuristic.manuallySelectedDictionaryTermOrNull(
                        source, settings.sourceLang, settings.translatorEngine),
                    onPartialTranslation = {}, onWordResult = {},
                )
                currentCoroutineContext().ensureActive()
                val presentation = processTextTranslationPresentation(outcome, "")
                if (presentation.translationSucceeded) {
                    logs.pair(LogRepository.Category.TRANSLATE, source, presentation.translation,
                        elapsedMs = (System.currentTimeMillis() - started).coerceAtLeast(0))
                } else {
                    logs.error(LogRepository.Category.TRANSLATE,
                        app.getString(R.string.process_text_translate_failed), outcome.translationError,
                        elapsedMs = (System.currentTimeMillis() - started).coerceAtLeast(0))
                }
                presentation
            }
        } as T
    }
}
