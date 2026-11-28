package dev.clickn.translate.data

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.translate.CommunityTranslationClient
import java.io.File
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class KeystoreSettingsRecoveryIntegrationTest {
    @Test fun aTemporaryFailurePreservesRealKeystoreCiphertextAcrossAColdReopen() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File(context.cacheDir, "keystore-recovery-${UUID.randomUUID()}.preferences_pb")
        val delegate = AndroidKeystoreSettingsSecretCipher(context)
        val unavailable = AtomicBoolean(false)
        val unreadablePayload = AtomicReference<String?>(null)
        val cipher = object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String {
                check(!unavailable.get())
                return delegate.encrypt(plainText)
            }
            override fun decrypt(cipherText: String): String {
                check(!unavailable.get() && cipherText != unreadablePayload.get())
                return delegate.decrypt(cipherText)
            }
        }
        val dummy = "synthetic-" + UUID.randomUUID()
        val endpoint = "https://keystore-fixture.example/v1"
        suspend fun withStore(check: suspend (SettingsRepository, suspend (String) -> String) -> Unit) {
            val job = SupervisorJob()
            val store = PreferenceDataStoreFactory.create(scope = CoroutineScope(job + Dispatchers.IO)) { file }
            try {
                check(SettingsRepository(context, cipher, store)) { key ->
                    requireNotNull(store.data.first()[stringPreferencesKey(key)])
                }
            } finally {
                job.cancelAndJoin()
            }
        }
        try {
            withStore { repo, stored ->
                repo.update { it.copy(baseUrl = endpoint, apiKey = dummy, translatorEngine = TranslatorEngine.LIBRETRANSLATE,
                    libreTranslateBaseUrl = endpoint, libreTranslateApiKey = dummy, sourceLang = "en", targetLang = "fr") }
                assertTrue(repo.get().apiKey == dummy)
                val ciphertext = stored("api_key")
                assertTrue(ciphertext.startsWith(SettingsSecretCodec.PREFIX))
                assertFalse(ciphertext.contains(dummy))

                // The key remains readable through Android Keystore but its address does not.
                unreadablePayload.set(stored("libre_url").removePrefix(SettingsSecretCodec.PREFIX))
                val attempts = AtomicInteger()
                val client = CommunityTranslationClient(OkHttpClient.Builder().addInterceptor {
                    attempts.incrementAndGet()
                    throw java.io.IOException("Fixture intercepts all network requests")
                }.build(), Json)
                val isolated = repo.get()
                val attempt = runCatching { client.translate("synthetic sample", isolated) }
                assertTrue("Unavailable provider addresses may not reach the transport", attempts.get() == 0)
                assertTrue(attempt.isFailure)
                assertTrue(isolated.libreTranslateApiKey.isEmpty())
                unreadablePayload.set(null)

                unavailable.set(true)
                assertEquals("", repo.get().apiKey)
                repo.update { it.copy(overlayAlpha = 0.67f) }
                val attemptedChange = runCatching { repo.update { it.copy(baseUrl = "https://other.example/v1") } }
                assertTrue(attemptedChange.exceptionOrNull() is SecureSettingsUnavailableException)
                assertTrue(stored("api_key") == ciphertext)
            }
            unavailable.set(false)
            withStore { reopened, _ ->
                val saved = reopened.get()
                assertTrue(saved.apiKey == dummy)
                assertTrue(saved.libreTranslateApiKey == dummy)
                assertEquals(endpoint, saved.baseUrl)
                assertEquals(0.67f, saved.overlayAlpha, 0.001f)
                reopened.update { it.copy(apiKey = "") }
                assertEquals("", reopened.get().apiKey)
            }
        } finally {
            file.delete()
        }
    }
}
