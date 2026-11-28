// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.stringPreferencesKey
import dev.clickn.translate.translate.CommunityTranslationClient
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.util.Base64
import java.util.zip.ZipInputStream
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.spec.GCMParameterSpec
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.encodeToJsonElement
import org.junit.Assert.*
import org.junit.Test
import org.junit.After

class PresetCredentialRepositoryTest {
    private val json = Json { encodeDefaults = true }
    private val storeScopes = mutableListOf<CoroutineScope>()

    @After
    fun closeStores() { storeScopes.forEach { it.cancel() } }

    @Test
    fun saveReopenSwitchAndOverwrite_tableDriven() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        val sources = listOf(
            Settings(baseUrl = "https://deepseek.test/v1", model = "deepseek", apiKey = "deepseek-secret"),
            Settings(baseUrl = "https://glm.test/v1", model = "glm", apiKey = "glm-secret"),
            Settings(baseUrl = "https://glm.test/v1", model = "glm", apiKey = "other-account-secret"),
            Settings(baseUrl = "http://localhost:8080/v1", model = "local", apiKey = ""),
            Settings(translatorEngine = TranslatorEngine.ANTHROPIC, anthropicApiKey = "anthropic-secret"),
        )
        val presets = sources.mapIndexed { index, settings -> preset("p$index", settings) }
        sources.zip(presets).forEach { (source, preset) -> repo.saveTranslationPreset(preset, source) }
        val reopened = fixture.repo()
        for (index in listOf(0, 1, 2, 0, 3, 4, 1)) {
            val result = requireNotNull(reopened.applyTranslationPreset(presets[index].id))
            val expected = sources[index]
            assertEquals(expected.model, result.model)
            assertEquals(expected.baseUrl, result.baseUrl)
            if (expected.translatorEngine == TranslatorEngine.ANTHROPIC) assertEquals(expected.anthropicApiKey, result.anthropicApiKey)
            else assertEquals(expected.apiKey, result.apiKey)
        }
        reopened.saveTranslationPreset(presets[0], sources[0].copy(apiKey = ""))
        assertEquals("", reopened.applyTranslationPreset(presets[0].id)?.apiKey)
        assertEquals("glm-secret", reopened.applyTranslationPreset(presets[1].id)?.apiKey)
        val raw = File(fixture.root, "datastore/clickntranslate_settings.preferences_pb").readBytes().toString(Charsets.ISO_8859_1)
        listOf("deepseek-secret", "glm-secret", "other-account-secret", "anthropic-secret").forEach { assertFalse(raw.contains(it)) }
    }

    @Test
    fun missingLegacyDeletedAndChangedEndpoint_useEmptyKey() = runBlocking {
        val repo = Fixture().repo()
        val source = Settings(apiKey = "secret", baseUrl = "https://original.test/v1")
        val p = preset("legacy", source)
        repo.update { source.copy(translationPresets = listOf(p)) }
        assertEquals("", repo.applyTranslationPreset(p.id)?.apiKey)
        repo.saveTranslationPreset(p, source)
        repo.update { it.copy(translationPresets = listOf(p.copy(baseUrl = "https://changed.test/v1"))) }
        assertEquals("", repo.applyTranslationPreset(p.id)?.apiKey)
        repo.update { it.copy(translationPresets = emptyList()) }
        repo.update { it.copy(translationPresets = listOf(p)) }
        assertEquals("", repo.applyTranslationPreset(p.id)?.apiKey)
        assertNull(repo.applyTranslationPreset("unknown"))
    }

    @Test
    fun sameConfigurationWithDifferentKeys_isRecognizedAsADifferentLocalPreset() = runBlocking {
        val repo = Fixture().repo()
        val a = Settings(apiKey = "key-a")
        val b = a.copy(apiKey = "key-b")
        repo.saveTranslationPreset(preset("a", a), a)
        repo.saveTranslationPreset(preset("b", b), b)
        assertTrue("a" in repo.matchingCredentialPresetIds(a))
        assertFalse("b" in repo.matchingCredentialPresetIds(a))
        assertTrue("b" in repo.matchingCredentialPresetIds(b))
        assertFalse("a" in repo.matchingCredentialPresetIds(b))
        assertTrue(repo.matchingCredentialPresetIds(a.copy(apiKey = "unsaved" )).isEmpty())
    }

    @Test
    fun encryptionFailure_preservesLastWorkingPresetAndRejectsReplacementAtomically() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        val source = Settings(apiKey = "never-plaintext", model = "keep-model", promptTemplate = "keep-prompt")
        val p = preset("failure", source)
        repo.saveTranslationPreset(p, source)
        val before = fixture.protectedValues(p.id)
        fixture.cipher.fail = true
        val edited = source.copy(apiKey = "replacement-secret", model = "replacement-model")
        val failed = runCatching { repo.saveTranslationPreset(preset(p.id, edited), edited) }
        assertTrue(failed.exceptionOrNull() is SecureSettingsUnavailableException)
        repo.update { it.copy(overlayAlpha = 0.63f) }
        assertTrue(before == fixture.protectedValues(p.id))
        fixture.cipher.fail = false
        val saved = fixture.repo().get()
        assertEquals(0.63f, saved.overlayAlpha, 0.001f)
        assertEquals("keep-model", saved.model)
        assertEquals("keep-prompt", saved.promptTemplate)
        assertEquals(p.id, saved.translationPresets.single().id)
        assertTrue(saved.apiKey == source.apiKey)
        assertTrue(repo.applyTranslationPreset(p.id)?.apiKey == source.apiKey)
        repo.saveTranslationPreset(preset(p.id, edited), edited)
        assertTrue(repo.applyTranslationPreset(p.id)?.apiKey == edited.apiKey)
        val raw = File(fixture.root, "datastore/clickntranslate_settings.preferences_pb").readBytes().toString(Charsets.ISO_8859_1)
        assertFalse(raw.contains("replacement-secret"))
        assertFalse(raw.contains("never-plaintext"))
        repo.saveTranslationPreset(p, source.copy(apiKey = ""))
        assertEquals("", repo.applyTranslationPreset(p.id)?.apiKey)
    }

    @Test
    fun unavailableDecryption_allowsAppearanceChangesWithoutReplacingKeysTheirEndpointOrPreset() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        val source = Settings(apiKey = "isolated-test-credential", baseUrl = "https://keystore-fixture.example/v1")
        val p = preset("locked", source)
        repo.saveTranslationPreset(p, source)
        val before = fixture.protectedValues(p.id)
        fixture.cipher.fail = true
        fixture.cipher.failRead = true
        assertEquals("", repo.get().apiKey)
        repo.update { it.copy(overlayAlpha = 0.71f) }
        val failed = runCatching { repo.update { it.copy(baseUrl = "https://other.example/v1", overlayAlpha = 0.15f) } }
        assertTrue(failed.exceptionOrNull() is SecureSettingsUnavailableException)
        assertTrue(before == fixture.protectedValues(p.id))
        fixture.cipher.fail = false
        fixture.cipher.failRead = false
        val reopened = fixture.repo().get()
        assertEquals(0.71f, reopened.overlayAlpha, 0.001f)
        assertEquals(source.baseUrl, reopened.baseUrl)
        assertTrue(reopened.apiKey == source.apiKey)
        assertEquals(p.id, reopened.translationPresets.single().id)
        assertTrue(repo.applyTranslationPreset(p.id)?.apiKey == source.apiKey)
    }

    @Test
    fun editingAPresetCannotEraseItsReadableKeyWhenOnlyTheGlobalKeyIsUnavailable() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        val source = Settings(apiKey = "synthetic-preset-key", baseUrl = "https://preset.example/v1")
        val p = preset("partially-locked", source)
        repo.saveTranslationPreset(p, source)
        val before = fixture.protectedValues(p.id)
        fixture.cipher.unreadableCiphertext = before.first().removePrefix(SettingsSecretCodec.PREFIX)
        assertEquals("", repo.get().apiKey)
        assertEquals(source.baseUrl, repo.get().baseUrl)
        val failed = runCatching { repo.saveTranslationPreset(p) }
        assertTrue(failed.exceptionOrNull() is SecureSettingsUnavailableException)
        assertTrue(before == fixture.protectedValues(p.id))
        fixture.cipher.unreadableCiphertext = null
        assertTrue(repo.applyTranslationPreset(p.id)?.apiKey == source.apiKey)
    }

    @Test
    fun cannotSendASavedKeyOrSourceTextToTheDefaultServerWhenTheCustomAddressIsUnreadable() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        val endpoint = "https://configured.example/v1"
        val dummy = "synthetic-libre-key"
        val hosts = java.util.Collections.synchronizedList(mutableListOf<String>())
        // This interceptor ends every request in memory, before any DNS or socket operation.
        val client = CommunityTranslationClient(OkHttpClient.Builder().addInterceptor { chain ->
            hosts += chain.request().url.host
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                .body("""{"translatedText":"synthetic result"}""".toResponseBody("application/json".toMediaType())).build()
        }.build(), json)
        repo.update { it.copy(translatorEngine = TranslatorEngine.LIBRETRANSLATE, sourceLang = "en", targetLang = "fr",
            libreTranslateBaseUrl = endpoint, libreTranslateApiKey = dummy) }
        assertEquals("synthetic result", client.translate("sample", repo.get()))
        assertEquals(listOf("configured.example"), hosts.toList())
        hosts.clear()
        fixture.cipher.unreadableCiphertext = fixture.encryptedValue("libre_url").removePrefix(SettingsSecretCodec.PREFIX)
        val unavailable = repo.get()
        val result = runCatching { client.translate("sample", unavailable) }
        assertTrue("No request may reach the transport while the selected address is unavailable", hosts.isEmpty())
        assertTrue(result.isFailure)
        assertTrue(unavailable.libreTranslateApiKey.isEmpty())
        val edit = runCatching { repo.update { it.copy(libreTranslateApiKey = "synthetic-replacement") } }
        assertTrue(edit.exceptionOrNull() is SecureSettingsUnavailableException)
        repo.update { it.copy(overlayAlpha = 0.62f) }
        fixture.cipher.unreadableCiphertext = null
        val restored = fixture.repo().get()
        assertTrue(restored.libreTranslateApiKey == dummy)
        assertEquals(endpoint, restored.libreTranslateBaseUrl)
        assertEquals(0.62f, restored.overlayAlpha, 0.001f)
        assertEquals("synthetic result", client.translate("sample", restored))
        assertEquals(listOf("configured.example"), hosts.toList())
    }

    @Test
    fun freshKeyWithNoKeystore_doesNotCommitAnUnusableProviderOrPlaintext() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        fixture.cipher.fail = true
        val original = repo.get()
        val dummy = "synthetic-new-key"
        val failed = runCatching {
            repo.update { it.copy(translatorEngine = TranslatorEngine.LIBRETRANSLATE, libreTranslateApiKey = dummy) }
        }
        assertTrue(failed.exceptionOrNull() is SecureSettingsUnavailableException)
        assertEquals(original.translatorEngine, repo.get().translatorEngine)
        assertEquals("", repo.get().libreTranslateApiKey)
        val file = File(fixture.root, "datastore/clickntranslate_settings.preferences_pb")
        assertFalse(file.exists() && file.readBytes().toString(Charsets.ISO_8859_1).contains(dummy))
    }

    @Test
    fun duplicateAndImportCollision_doNotBorrowGlobalOrSameNameCredentials() = runBlocking {
        for (sameId in listOf(true, false)) {
            val repo = Fixture().repo()
            val source = Settings(apiKey = "original-secret")
            val p = preset("original", source)
            repo.saveTranslationPreset(p, source)
            repo.update { it.copy(apiKey = "global-other-secret") }
            val duplicate = requireNotNull(repo.duplicateTranslationPreset(p.id, "copy", "copy"))
            assertEquals("original-secret", repo.applyTranslationPreset(duplicate.id)?.apiKey)
            val imported = p.copy(id = if (sameId) p.id else "new-imported-id")
            repo.updateAfterPresetImport(setOf(imported.name)) { current ->
                current.copy(translationPresets = TranslationPresetTransfer.mergeImportedPresets(current.translationPresets, listOf(imported)).presets)
            }
            assertEquals("", repo.applyTranslationPreset(p.id)?.apiKey)
            assertEquals("original-secret", repo.applyTranslationPreset(duplicate.id)?.apiKey)
        }
    }

    @Test
    fun concurrentSwitchAndSaveThenApply_keepAddressModelAndKeyTogether() = runBlocking {
        val repo = Fixture().repo()
        val a = Settings(baseUrl = "https://a.test", model = "a", apiKey = "key-a")
        val b = Settings(baseUrl = "https://b.test", model = "b", apiKey = "key-b")
        repo.saveTranslationPreset(preset("a", a), a)
        repo.saveTranslationPreset(preset("b", b), b)
        (0 until 12).map { index -> async {
            val expected = if (index % 2 == 0) a else b
            val result = requireNotNull(repo.applyTranslationPreset(expected.model))
            assertEquals(expected.baseUrl, result.baseUrl)
            assertEquals(expected.apiKey, result.apiKey)
        } }.awaitAll()
        repo.update { a.copy(translationPresets = it.translationPresets, apiKey = "new-a") }
        assertEquals("key-b", repo.applyTranslationPreset("b", preset("saved-draft", a))?.apiKey)
        assertEquals("new-a", repo.applyTranslationPreset("saved-draft")?.apiKey)
    }

    @Test
    fun gallerySnapshotKeepsItsOwnCredentialsWithoutSwitchingActivePreset() = runBlocking {
        val repo = Fixture().repo()
        val original = Settings(apiKey = "gallery-secret", baseUrl = "https://gallery.test")
        val snapshot = preset("gallery_test", original)
        repo.rememberSnapshotCredentials(snapshot, original)
        repo.update { it.copy(apiKey = "other-secret", activeTranslationPresetId = "other", baseUrl = "https://other.test") }
        assertEquals("gallery-secret", repo.settingsForSnapshot(snapshot).apiKey)
        assertEquals("other", repo.get().activeTranslationPresetId)
        repo.forgetSnapshotCredentials(snapshot.id)
        assertEquals("", repo.settingsForSnapshot(snapshot).apiKey)
    }

    @Test
    fun exports_tableDriven_neverContainCredentialValuesOrLocalCiphertext() = runBlocking {
        val fixture = Fixture()
        val repo = fixture.repo()
        val source = PresetCredentialPolicyTest().withCredentials(Settings(), "export-forbidden")
        repo.update { source }
        repo.saveTranslationPreset(preset("export", source), source)
        val settings = repo.get()
        val output = ByteArrayOutputStream()
        SettingsBundleTransfer.write(output, settings) { null }
        val manifest = ZipInputStream(output.toByteArray().inputStream()).use { zip ->
            zip.nextEntry
            zip.readBytes().toString(Charsets.UTF_8)
        }
        val legacyRoundTrip = TranslationPresetTransfer.decodeEncrypted(TranslationPresetTransfer.encodeEncrypted(settings.translationPresets))
        val candidates = listOf(manifest, json.encodeToJsonElement(legacyRoundTrip).toString(), SettingsFieldPolicy.formatDiagnostics(settings))
        for (text in candidates) {
            assertFalse(text.contains("export-forbidden"))
            assertFalse(text.contains("local_preset_credentials"))
            assertFalse(text.contains("PresetCredentialRecord"))
            fixture.cipher.ciphertexts.forEach { assertFalse(text.contains(it)) }
        }
    }

    private fun preset(id: String, source: Settings) = TranslationPresetCatalog.fromSettings(id, id, id, source)

    private inner class Fixture {
        val root: File = Files.createTempDirectory("preset-credential-test").toFile()
        val cipher = TestCipher()
        private val store = PreferenceDataStoreFactory.create(
            scope = CoroutineScope(SupervisorJob() + Dispatchers.IO).also(storeScopes::add),
        ) { File(root, "datastore/clickntranslate_settings.preferences_pb") }
        suspend fun encryptedValue(name: String): String =
            requireNotNull(store.data.first()[stringPreferencesKey(name)]).also {
                assertTrue(it.startsWith(SettingsSecretCodec.PREFIX))
            }
        suspend fun protectedValues(id: String): List<String> {
            val prefs = store.data.first()
            return listOf("api_key", "base_url", "translation_presets_json", "local_preset_credentials_v1_$id").map {
                requireNotNull(prefs[stringPreferencesKey(it)]).also { stored ->
                    assertTrue(stored.startsWith(SettingsSecretCodec.PREFIX))
                }
            }
        }
        fun repo() = SettingsRepository(object : ContextWrapper(null) {
            override fun getApplicationContext(): Context = this
            override fun getFilesDir(): File = root
            override fun getPackageName(): String = "dev.clickn.translate.presettest"
        }, cipher, store).apply { setDefaultPromptProvidersForTest({ "default prompt" }, { "default dictionary" }) }
    }

    private class TestCipher : SettingsSecretCipher {
        var fail = false
        var failRead = false
        var unreadableCiphertext: String? = null
        val ciphertexts = mutableListOf<String>()
        private val key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        override fun encrypt(plainText: String): String {
            check(!fail)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
            return Base64.getEncoder().encodeToString(cipher.iv + cipher.doFinal(plainText.toByteArray())).also(ciphertexts::add)
        }
        override fun decrypt(cipherText: String): String {
            check(!failRead && cipherText != unreadableCiphertext)
            val bytes = Base64.getDecoder().decode(cipherText)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes.copyOfRange(0, 12))) }
            return cipher.doFinal(bytes.copyOfRange(12, bytes.size)).toString(Charsets.UTF_8)
        }
    }
}
