package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import java.io.File
import java.nio.file.Files
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertTrue
import org.junit.Test

/** Real isolated DataStore transactions own the selection revision; no fake revision counter. */
class SettingsSelectionRevisionIntegrationTest {
    private val initial = Settings(
        translatorEngine = TranslatorEngine.GOOGLE,
        sourceLang = "en",
        targetLang = "ru",
    )

    @Test fun bothSettingsFlowsDecodePreferencesOffTheCollectorThread() = runBlocking {
        withRepository { repository ->
            val caller = Thread.currentThread()
            val decodes = AtomicInteger()
            repository.setDefaultPromptProvidersForTest({
                assertNotSame("Preference decoding must not block the collector", caller, Thread.currentThread())
                decodes.incrementAndGet()
                "fixture prompt"
            }, { "fixture dictionary" })

            val settings = repository.settings.first()
            val publicDecodes = decodes.get()
            assertTrue(publicDecodes > 0)

            assertEquals(settings, repository.selectionSnapshots.first().settings)
            assertTrue(decodes.get() > publicDecodes)
        }
    }

    @Test fun engineAndEitherLanguageChangeAndRevertPreventPendingActivation() = runBlocking {
        val laterChoices: List<(Settings) -> Settings> = listOf(
            { it.copy(translatorEngine = TranslatorEngine.LINGVA) },
            { it.copy(sourceLang = "ja") },
            { it.copy(targetLang = "fr") },
        )
        for (chooseLater in laterChoices) withRepository { repository ->
            coroutineScope {
                val baseline = repository.selectionSnapshots.first()
                val requested = baseline.settings.copy(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT)
                val downloaded = CompletableDeferred<Unit>()
                val activation = launch {
                    downloaded.await()
                    repository.updateTranslationSelectionIfUnchanged(baseline, requested)
                }

                repository.update(chooseLater)
                repository.update { current -> current.copy(
                    translatorEngine = baseline.settings.translatorEngine,
                    sourceLang = baseline.settings.sourceLang,
                    targetLang = baseline.settings.targetLang,
                ) }
                assertEquals(baseline.revision + 2, repository.selectionSnapshots.first().revision)
                downloaded.complete(Unit)
                activation.join()

                assertEquals(baseline.settings, repository.get())
                assertEquals(baseline.revision + 2, repository.selectionSnapshots.first().revision)
            }
        }
    }

    @Test fun unrelatedEditsAllowActivationAndArePreserved() = runBlocking {
        withRepository { repository ->
            val baseline = repository.selectionSnapshots.first()
            val requested = baseline.settings.copy(
                translatorEngine = TranslatorEngine.GOOGLE_ML_KIT,
                sourceLang = "ja",
                targetLang = "fr",
            )
            repository.update { it.copy(overlayAlpha = 0.42f, apiTimeoutSeconds = 43) }
            // Effective value changes own the revision; repeated same-value intent is a separate contract.
            repository.update { it.copy(sourceLang = baseline.settings.sourceLang) }
            assertEquals(baseline.revision, repository.selectionSnapshots.first().revision)

            repository.updateTranslationSelectionIfUnchanged(baseline, requested)

            assertEquals(requested.copy(overlayAlpha = 0.42f, apiTimeoutSeconds = 43), repository.get())
            assertEquals(baseline.revision + 1, repository.selectionSnapshots.first().revision)
        }
    }

    @Test fun liveAndRawImportRollbackCannotReenableAnOlderActivation() = runBlocking {
        for (rawRecovery in listOf(false, true)) withRepository { repository ->
            val baseline = repository.selectionSnapshots.first()
            val requested = baseline.settings.copy(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT)
            var journalChanges = emptyList<ImportPreferenceChange>()
            val rollback = SettingsImportRollback { journalChanges = it }
            repository.updateImportedSettings(emptySet(), rollback) { current -> current.copy(
                translatorEngine = TranslatorEngine.LINGVA,
                sourceLang = "ja",
            ) }
            assertEquals(baseline.revision + 1, repository.selectionSnapshots.first().revision)
            assertFalse(journalChanges.any { it.name == TranslationSelectionRevision.key.name })
            repository.update { it.copy(overlayAlpha = 0.42f) }

            if (rawRecovery) repository.recoverImportedSettings(journalChanges)
            else repository.rollbackImportedSettings(rollback)

            val restored = repository.selectionSnapshots.first()
            assertEquals(baseline.settings.copy(overlayAlpha = 0.42f), restored.settings)
            assertEquals(baseline.revision + 2, restored.revision)
            repository.updateTranslationSelectionIfUnchanged(baseline, requested)
            assertEquals(restored, repository.selectionSnapshots.first())
        }
    }

    @Test fun liveAndRawRestoreIgnoreTheReservedRevisionKey() = runBlocking {
        for (rawRecovery in listOf(false, true)) withRepository { repository ->
            val before = repository.selectionSnapshots.first()
            repository.update { it.copy(targetLang = "fr") }
            val current = repository.selectionSnapshots.first()
            // Even a checkpoint containing metadata cannot turn the revision back into an old token.
            val changes = listOf(ImportPreferenceChange(
                TranslationSelectionRevision.key.name,
                ImportPreferenceValues.encode(before.revision),
                ImportPreferenceValues.encode(current.revision),
            ))

            if (rawRecovery) repository.recoverImportedSettings(changes)
            else repository.rollbackImportedSettings(SettingsImportRollback.restoreToken(changes))

            assertEquals(current, repository.selectionSnapshots.first())
        }
    }

    @Test fun revisionPersistsAcrossColdStoreReopenAndKeepsOldTokensInvalid() = runBlocking {
        withReopenableRepository { repository, reopen ->
            val baseline = repository.selectionSnapshots.first()
            val requested = baseline.settings.copy(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT)
            repository.update { it.copy(translatorEngine = TranslatorEngine.LINGVA) }
            repository.update { it.copy(translatorEngine = baseline.settings.translatorEngine) }
            val afterRevert = repository.selectionSnapshots.first()

            val reopened = reopen()
            assertEquals(afterRevert, reopened.selectionSnapshots.first())
            reopened.updateTranslationSelectionIfUnchanged(baseline, requested)
            assertEquals(afterRevert, reopened.selectionSnapshots.first())
            reopened.updateTranslationSelectionIfUnchanged(afterRevert, requested)
            assertEquals(requested, reopened.get())
            assertEquals(afterRevert.revision + 1, reopened.selectionSnapshots.first().revision)
        }
    }

    private suspend fun withRepository(action: suspend (SettingsRepository) -> Unit) =
        withReopenableRepository { repository, _ -> action(repository) }

    private suspend fun withReopenableRepository(
        action: suspend (SettingsRepository, suspend () -> SettingsRepository) -> Unit,
    ) {
        val root = Files.createTempDirectory("translation-selection-revision").toFile()
        val file = File(root, "settings.preferences_pb")
        var storage = SettingsStorage(file)
        try {
            val repository = createRepository(root, storage)
            repository.update { initial }
            action(repository) {
                storage.closeAndJoin()
                storage = SettingsStorage(file)
                createRepository(root, storage)
            }
        } finally {
            storage.closeAndJoin()
            check(root.canonicalFile.parentFile == File(System.getProperty("java.io.tmpdir")).canonicalFile)
            check(root.name.startsWith("translation-selection-revision"))
            root.deleteRecursively()
        }
    }

    private fun createRepository(root: File, storage: SettingsStorage): SettingsRepository =
        SettingsRepository(object : ContextWrapper(null) {
            override fun getApplicationContext(): Context = this
            override fun getFilesDir(): File = root
            override fun getPackageName(): String = "dev.clickn.translate.selectiontest"
        }, FixtureCipher, storage.dataStore).apply {
            setDefaultPromptProvidersForTest({ "fixture prompt" }, { "fixture dictionary" })
        }

    private object FixtureCipher : SettingsSecretCipher {
        override fun encrypt(plainText: String): String = "fixture:$plainText"
        override fun decrypt(cipherText: String): String = cipherText.removePrefix("fixture:")
    }
}
