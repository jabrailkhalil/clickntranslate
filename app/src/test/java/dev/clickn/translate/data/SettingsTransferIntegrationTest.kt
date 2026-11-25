package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.Base64
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test

/** Real ZIP codec, file-backed DataStore and encrypted profile records; no Android keystore changes. */
class SettingsTransferIntegrationTest {
    @Test fun roundTripAndCancelledCommitPreserveProfilesLocalSecretsAndUnrelatedEdits() = runBlocking {
        val root = Files.createTempDirectory("settings-transfer-integration").toFile()
        val storeJob = SupervisorJob()
        val storeScope = CoroutineScope(storeJob + Dispatchers.IO)
        val store = PreferenceDataStoreFactory.create(scope = storeScope) {
            File(root, "settings.preferences_pb")
        }
        val repository = SettingsRepository(object : ContextWrapper(null) {
            override fun getApplicationContext(): Context = this
            override fun getFilesDir(): File = root
            override fun getPackageName(): String = "dev.clickn.translate.settingstest"
        }, LocalFixtureCipher(), store).apply {
            setDefaultPromptProvidersForTest({ "fixture prompt" }, { "fixture dictionary" })
        }
        try {
            val a = Settings(sourceLang = "en", targetLang = "ru", translatorEngine = TranslatorEngine.OPENAI,
                baseUrl = "https://a.example.invalid/v1", apiKey = "synthetic-local-a", model = "model-a")
            val b = a.copy(baseUrl = "https://b.example.invalid/v1", apiKey = "synthetic-local-b", model = "model-b")
            val profileA = TranslationPresetCatalog.fromSettings("custom_a", "Profile A", "A", a)
            val profileB = TranslationPresetCatalog.fromSettings("custom_b", "Profile B", "B", b)
            repository.saveTranslationPreset(profileA, a)
            repository.saveTranslationPreset(profileB, b)
            val before = repository.get()
            val existingSnapshot = TranslationPresetCatalog.fromSettings("gallery_before", "Before", "B", a)
            repository.rememberSnapshotCredentials(existingSnapshot, a)

            val remote = a.copy(targetLang = "ar", model = "portable-model",
                anthropicBaseUrl = "https://example.invalid/anthropic?token=synthetic-private",
                lingvaBaseUrl = "https://example.invalid/lingva?token=synthetic-private",
                libreTranslateBaseUrl = "https://example.invalid/libre?token=synthetic-private")
            val remoteProfile = TranslationPresetCatalog.fromSettings("custom_remote", "Profile A", "A", remote)
            val output = ByteArrayOutputStream()
            SettingsBundleTransfer.write(output, remote.copy(translationPresets = listOf(remoteProfile),
                activeTranslationPresetId = remoteProfile.id)) { null }
            val bytes = output.toByteArray()
            val manifest = ZipInputStream(bytes.inputStream()).use { zip ->
                assertEquals("manifest.json", zip.nextEntry.name)
                zip.readBytes().toString(Charsets.UTF_8)
            }
            listOf("synthetic-local-a", "synthetic-private", "a.example.invalid").forEach {
                assertFalse("Private connection/credential must not be exported", manifest.contains(it))
            }
            val preview = SettingsBundleTransfer.read(bytes.inputStream()) { _, _ -> fail("No fonts expected") }
            val imported = requireNotNull(preview.settings)
            assertEquals("ar", imported.targetLang)
            assertEquals(Settings().anthropicBaseUrl, imported.translationPresets.single().anthropicBaseUrl)
            val checkpoint = SettingsImportRollback()
            val committed = CompletableDeferred<Unit>()
            val newSnapshot = TranslationPresetCatalog.fromSettings("gallery_during", "During", "D", a)
            val importJob = launch {
                try {
                    repository.updateImportedSettings(setOf("Profile A"), checkpoint) { current ->
                        SettingsBundleTransfer.mergeImportedSettings(current, imported, emptyList(),
                            preview.appliedSettingFields).settings
                    }
                    committed.complete(Unit)
                    awaitCancellation()
                } finally {
                    withContext(NonCancellable) { repository.rollbackImportedSettings(checkpoint) }
                }
            }
            committed.await()
            assertEquals("portable-model", repository.get().model)
            repository.update { it.copy(overlayAlpha = 0.42f) }
            repository.rememberSnapshotCredentials(newSnapshot, a)
            importJob.cancelAndJoin()
            val restored = repository.get()
            assertEquals(before.translationPresets, restored.translationPresets)
            assertEquals(before.activeTranslationPresetId, restored.activeTranslationPresetId)
            assertEquals(before.apiKey, restored.apiKey)
            assertEquals(before.targetLang, restored.targetLang)
            assertEquals(0.42f, restored.overlayAlpha)
            assertEquals("synthetic-local-a", repository.settingsForSnapshot(existingSnapshot).apiKey)
            assertEquals("synthetic-local-a", repository.settingsForSnapshot(newSnapshot).apiKey)
            assertEquals("synthetic-local-a", repository.applyTranslationPreset(profileA.id)?.apiKey)
            assertEquals("synthetic-local-b", repository.applyTranslationPreset(profileB.id)?.apiKey)

            val fontName = "0".repeat(64) + ".ttf"
            repository.update { it.copy(overlayFontFileName = fontName, overlayFontDisplayName = "Existing.ttf",
                overlayFonts = listOf(OverlayFontEntry(fontName, "Existing.ttf"))) }
            val beforePartial = repository.get()
            val partial = SettingsBundleTransfer.read(fixture("partial-v2.json").inputStream()) { _, _ -> fail() }
            assertEquals(listOf("translatorEngine"), partial.skippedSettingFields)
            repository.updateAfterPresetImport(emptySet()) { current ->
                SettingsBundleTransfer.mergeImportedSettings(current, requireNotNull(partial.settings),
                    current.overlayFonts, partial.appliedSettingFields).settings
            }
            val afterPartial = repository.get()
            assertEquals("ar", afterPartial.targetLang)
            assertEquals(19, afterPartial.overlayTextSizeSp)
            assertEquals(beforePartial.translatorEngine, afterPartial.translatorEngine)
            assertEquals(beforePartial.model, afterPartial.model)
            assertEquals(beforePartial.apiKey, afterPartial.apiKey)
            assertEquals(beforePartial.overlayAlpha, afterPartial.overlayAlpha)
            assertEquals(beforePartial.overlayFontFileName, afterPartial.overlayFontFileName)
            assertEquals(beforePartial.translationPresets, afterPartial.translationPresets)

            assertTrue(runCatching {
                SettingsBundleTransfer.read(fixture("missing-font-v2.json").inputStream()) { _, _ -> fail() }
            }.isFailure)
            assertEquals(afterPartial, repository.get())
            val oversized = ByteArrayOutputStream()
            assertTrue(runCatching {
                SettingsBundleTransfer.write(oversized, a.copy(promptTemplate = "x".repeat(2 * 1024 * 1024))) { null }
            }.isFailure)
            assertEquals("An unreadable oversized manifest must fail before writing the destination", 0, oversized.size())
            val stored = File(root, "settings.preferences_pb").readBytes().toString(Charsets.ISO_8859_1)
            assertFalse(stored.contains("synthetic-local-a"))
            assertFalse(stored.contains("synthetic-local-b"))
        } finally {
            storeScope.cancel()
            storeJob.join()
            root.deleteRecursively()
        }
    }

    private fun fixture(name: String): ByteArray = ByteArrayOutputStream().also { output ->
        val manifest = requireNotNull(javaClass.getResourceAsStream("/settings-transfer/$name")).use { it.readBytes() }
        ZipOutputStream(output).use { zip ->
            zip.putNextEntry(ZipEntry("manifest.json"))
            zip.write(manifest)
            zip.closeEntry()
        }
    }.toByteArray()

    private class LocalFixtureCipher : SettingsSecretCipher {
        private val key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        override fun encrypt(plainText: String): String = Cipher.getInstance("AES/GCM/NoPadding").run {
            init(Cipher.ENCRYPT_MODE, key)
            Base64.getEncoder().encodeToString(iv + doFinal(plainText.toByteArray(Charsets.UTF_8)))
        }
        override fun decrypt(cipherText: String): String {
            val bytes = Base64.getDecoder().decode(cipherText)
            return Cipher.getInstance("AES/GCM/NoPadding").run {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
                doFinal(bytes.copyOfRange(12, bytes.size)).toString(Charsets.UTF_8)
            }
        }
    }
}
