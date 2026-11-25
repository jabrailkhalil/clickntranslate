package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import dev.clickn.translate.ui.SettingsEditingSnapshot
import dev.clickn.translate.ui.observeSettingsEditing
import java.io.File
import java.nio.file.Files
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test

/** Production repository + file-backed DataStore, with a deterministic delayed provider commit. */
class SettingsEditorPersistenceIntegrationTest {
    @Test fun cleanEditorReceivesProviderCommitThatFinishesAfterItsInitialRead() = runBlocking {
        withOwnedStore { repository, _ ->
            val before = seed(repository)
            val entered = CompletableDeferred<Unit>()
            val release = CountDownLatch(1)
            val writer = async(Dispatchers.IO) {
                repository.update { latest ->
                    entered.complete(Unit)
                    check(release.await(5, TimeUnit.SECONDS))
                    providerAfter(latest)
                }
            }
            val editor = MutableStateFlow(SettingsEditingSnapshot(before, before))
            val observer = launch(start = CoroutineStart.UNDISPATCHED) {
                observeSettingsEditing(editor.value, repository.settings, { editor.value }, { editor.value = it })
            }
            try {
                withTimeout(5_000) { entered.await() }
                assertEquals(TranslatorEngine.GOOGLE_ML_KIT, repository.get().translatorEngine)
                assertEquals(TranslatorEngine.GOOGLE_ML_KIT, editor.value.draft.translatorEngine)
                release.countDown()
                withTimeout(5_000) { writer.await() }
                val updated = withTimeout(5_000) {
                    editor.first { it.draft.translatorEngine == TranslatorEngine.OPENAI }
                }
                assertEquals("synthetic-after", updated.draft.apiKey)
                assertEquals("late-model", updated.draft.model)
                assertEquals(updated.persisted, updated.draft)
                assertEquals(repository.get(), updated.persisted)
            } finally {
                release.countDown()
                observer.cancelAndJoin()
                writer.cancelAndJoin()
            }
        }
    }

    @Test fun queuedDirtySaveMergesItsFieldsWithoutOverwritingLaterProviderOrExportMetadata() = runBlocking {
        withOwnedStore { repository, file ->
            val before = seed(repository)
            val draft = before.copy(captureLoopIntervalMs = 4_400, overlayAlpha = 0.61f,
                promptTemplate = "Owned editor paragraph العربية")
            val preset = TranslationPresetCatalog.fromSettings("custom_late", "Late profile", "L", before)
            val entered = CompletableDeferred<Unit>()
            val release = CountDownLatch(1)
            val writer = async(Dispatchers.IO) {
                repository.update { latest ->
                    entered.complete(Unit)
                    check(release.await(5, TimeUnit.SECONDS))
                    providerAfter(latest).copy(translationPresets = listOf(preset), activeTranslationPresetId = preset.id,
                        pinnedLanguages = listOf("ar"), captureRegionSavedScreenW = 1080, captureRegionSavedScreenH = 2400)
                }
            }
            var saving: kotlinx.coroutines.Deferred<Settings>? = null
            try {
                withTimeout(5_000) { entered.await() }
                val save = async(start = CoroutineStart.UNDISPATCHED) { repository.saveEditorChanges(before, draft) }
                saving = save
                assertFalse(save.isCompleted)
                release.countDown()
                withTimeout(5_000) { writer.await() }
                val saved = withTimeout(5_000) { save.await() }
                assertEquals(TranslatorEngine.OPENAI, saved.translatorEngine)
                assertEquals("https://late.example.invalid/v1", saved.baseUrl)
                assertEquals("synthetic-after", saved.apiKey)
                assertEquals("late-model", saved.model)
                assertEquals(4_400L, saved.captureLoopIntervalMs)
                assertEquals(0.61f, saved.overlayAlpha)
                assertEquals(draft.promptTemplate, saved.promptTemplate)
                assertEquals(listOf(preset), saved.translationPresets)
                assertEquals(preset.id, saved.activeTranslationPresetId)
                assertEquals(listOf("ar"), saved.pinnedLanguages)
                assertEquals(1080, saved.captureRegionSavedScreenW)
                assertEquals(2400, saved.captureRegionSavedScreenH)
                assertFalse(file.readBytes().toString(Charsets.ISO_8859_1).contains("synthetic-after"))
            } finally {
                release.countDown()
                saving?.cancelAndJoin()
                writer.cancelAndJoin()
            }
        }
    }

    private suspend fun seed(repository: SettingsRepository): Settings {
        repository.update { Settings(sourceLang = "en", targetLang = "ru", promptTemplate = "Owned prompt",
            translatorEngine = TranslatorEngine.GOOGLE_ML_KIT, baseUrl = "https://before.example.invalid/v1",
            apiKey = "synthetic-before", model = "before-model") }
        return repository.get()
    }

    private fun providerAfter(value: Settings) = value.copy(translatorEngine = TranslatorEngine.OPENAI,
        baseUrl = "https://late.example.invalid/v1", apiKey = "synthetic-after", model = "late-model")

    private suspend fun withOwnedStore(action: suspend (SettingsRepository, File) -> Unit) {
        val parent = File(System.getProperty("java.io.tmpdir")).canonicalFile
        val root = Files.createTempDirectory(parent.toPath(), "settings-editor-state-").toFile()
        val job = SupervisorJob()
        val scope = CoroutineScope(job + Dispatchers.IO)
        val file = File(root, "settings.preferences_pb")
        val store = PreferenceDataStoreFactory.create(scope = scope) { file }
        val repository = SettingsRepository(object : ContextWrapper(null) {
            override fun getApplicationContext(): Context = this
            override fun getFilesDir(): File = root
            override fun getPackageName(): String = "dev.clickn.translate.editorfixture"
        }, object : SettingsSecretCipher {
            // Encoding fixture only; production encryption is tested by its own integration cases.
            override fun encrypt(plainText: String): String = Base64.getEncoder().encodeToString(plainText.toByteArray())
            override fun decrypt(cipherText: String): String = Base64.getDecoder().decode(cipherText).toString(Charsets.UTF_8)
        }, store).apply { setDefaultPromptProvidersForTest({ "Owned prompt" }, { "Owned dictionary" }) }
        try { withTimeout(15_000) { action(repository, file) } }
        finally {
            job.cancelAndJoin()
            check(root.canonicalFile.parentFile == parent && root.name.startsWith("settings-editor-state-"))
            check(root.deleteRecursively())
        }
    }
}
