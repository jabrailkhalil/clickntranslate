package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.mutablePreferencesOf
import androidx.datastore.preferences.core.stringPreferencesKey
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.Assert.*
import org.junit.Test

class SettingsRepositoryRecoveryGateTest {
    @Test fun publicSettingsAndGetNeverSubscribeToRawStorageBeforeRecoveryOrAfterItsFailure() = runBlocking {
        val target = stringPreferencesKey("target_lang")
        val values = MutableStateFlow<Preferences>(mutablePreferencesOf(target to "ar"))
        val subscriptions = AtomicInteger()
        val rawStore = object : DataStore<Preferences> {
            override val data: Flow<Preferences> = flow { subscriptions.incrementAndGet(); emitAll(values) }
            override suspend fun updateData(transform: suspend (Preferences) -> Preferences): Preferences =
                transform(values.value).also { values.value = it }
        }
        val gate = SettingsImportRecoveryGate.pendingForTest()
        val context = object : ContextWrapper(null) { override fun getApplicationContext(): Context = this }
        val repository = SettingsRepository(context, object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String = "fixture:$plainText"
            override fun decrypt(cipherText: String): String = cipherText.removePrefix("fixture:")
        }, rawStore, gate).apply { setDefaultPromptProvidersForTest({ "fixture prompt" }, { "fixture dictionary" }) }
        val get = async(start = CoroutineStart.UNDISPATCHED) { repository.get() }
        val observe = async(start = CoroutineStart.UNDISPATCHED) { repository.settings.first() }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            // Return Unit so a regression cannot print Settings/credentials through Assert.toString.
            assertNull(withTimeoutOrNull(100) { get.await(); Unit })
            assertNull(withTimeoutOrNull(100) { observe.await(); Unit })
            assertEquals(0, subscriptions.get())
            var attempts = 0
            gate.start(scope) {
                if (++attempts == 1) error("fixture recovery rejected")
                values.value = mutablePreferencesOf(target to "fr")
            }
            withTimeout(5_000) { gate.state.first { it == SettingsImportRecoveryState.FAILED } }
            assertNull(withTimeoutOrNull(100) { get.await(); Unit })
            assertNull(withTimeoutOrNull(100) { observe.await(); Unit })
            assertEquals(0, subscriptions.get())
            gate.retry()
            assertEquals("fr", withTimeout(5_000) { get.await() }.targetLang)
            assertEquals("fr", withTimeout(5_000) { observe.await() }.targetLang)
            assertEquals(2, subscriptions.get())
        } finally { get.cancelAndJoin(); observe.cancelAndJoin(); scope.cancel() }
    }
}
