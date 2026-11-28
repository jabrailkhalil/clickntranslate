package dev.clickn.translate.data

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
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
        val cipher = object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String {
                check(!unavailable.get())
                return delegate.encrypt(plainText)
            }
            override fun decrypt(cipherText: String): String {
                check(!unavailable.get())
                return delegate.decrypt(cipherText)
            }
        }
        val dummy = "synthetic-" + UUID.randomUUID()
        val endpoint = "https://keystore-fixture.example/v1"
        suspend fun withStore(check: suspend (SettingsRepository, suspend () -> String) -> Unit) {
            val job = SupervisorJob()
            val store = PreferenceDataStoreFactory.create(scope = CoroutineScope(job + Dispatchers.IO)) { file }
            try {
                check(SettingsRepository(context, cipher, store)) {
                    requireNotNull(store.data.first()[stringPreferencesKey("api_key")])
                }
            } finally {
                job.cancelAndJoin()
            }
        }
        try {
            withStore { repo, storedCredential ->
                repo.update { it.copy(baseUrl = endpoint, apiKey = dummy) }
                assertTrue(repo.get().apiKey == dummy)
                val ciphertext = storedCredential()
                assertTrue(ciphertext.startsWith(SettingsSecretCodec.PREFIX))
                assertFalse(ciphertext.contains(dummy))

                unavailable.set(true)
                assertEquals("", repo.get().apiKey)
                repo.update { it.copy(overlayAlpha = 0.67f) }
                val attemptedChange = runCatching { repo.update { it.copy(baseUrl = "https://other.example/v1") } }
                assertTrue(attemptedChange.exceptionOrNull() is SecureSettingsUnavailableException)
                assertTrue(storedCredential() == ciphertext)
            }
            unavailable.set(false)
            withStore { reopened, _ ->
                val saved = reopened.get()
                assertTrue(saved.apiKey == dummy)
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
