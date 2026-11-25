package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import java.io.File
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** Real file-backed DataStores: distinct Application roots, shared ownership and deterministic closure. */
class SettingsStorageOwnershipTest {
    @get:Rule val temporary = TemporaryFolder()

    @Test fun distinctApplicationRootsNeverReuseTheFirstApplicationsFile() = runBlocking {
        val rootA = temporary.newFolder("application-a")
        val rootB = temporary.newFolder("application-b")
        val a = SettingsStorage(FileContext(rootA))
        val b = SettingsStorage(FileContext(rootB))
        val key = stringPreferencesKey("owned-fixture")
        try {
            a.dataStore.edit { it[key] = "A" }
            assertNull(b.dataStore.data.first()[key])
            b.dataStore.edit { it[key] = "B" }
            assertEquals("A", a.dataStore.data.first()[key])
            assertEquals("B", b.dataStore.data.first()[key])
            assertTrue(File(rootA, PATH).isFile)
            assertTrue(File(rootB, PATH).isFile)
        } finally { a.closeAndJoin(); b.closeAndJoin() }
    }

    @Test fun recreatedRepositoriesShareOneOwnerAndAClosedOwnerCanBeReopenedFromDisk() = runBlocking {
        val context = FileContext(temporary.newFolder("application"))
        val storage = SettingsStorage(context)
        try {
            val first = repository(context, storage)
            val second = repository(context, storage)
            first.update { it.copy(targetLang = "ar", apiTimeoutSeconds = 43) }
            assertEquals("ar", second.get().targetLang)
            assertEquals(43, second.get().apiTimeoutSeconds)
            storage.closeAndJoin()
            assertTrue(storage.isClosed)
            val replacement = SettingsStorage(context)
            try {
                val reopened = repository(context, replacement)
                assertEquals("ar", reopened.get().targetLang)
                assertEquals(43, reopened.get().apiTimeoutSeconds)
            } finally { replacement.closeAndJoin() }
        } finally { storage.closeAndJoin() }
    }

    @Test fun closingOneOwnerRejectsFurtherWritesAndDoesNotCancelAnotherOwner() = runBlocking {
        val a = SettingsStorage(FileContext(temporary.newFolder("application-a")))
        val b = SettingsStorage(FileContext(temporary.newFolder("application-b")))
        val key = stringPreferencesKey("owned-fixture")
        try {
            a.dataStore.edit { it[key] = "persisted" }
            a.closeAndJoin()
            val failure = runCatching {
                withTimeout(5_000) { a.dataStore.edit { it[key] = "must-not-write" } }
            }.exceptionOrNull()
            assertNotNull("A closed owner's IO scope must reject writes", failure)
            assertFalse("A closed owner must fail promptly rather than leave a hung writer", failure is TimeoutCancellationException)
            b.dataStore.edit { it[key] = "independent" }
            assertEquals("independent", b.dataStore.data.first()[key])
        } finally { a.closeAndJoin(); b.closeAndJoin() }
    }

    private fun repository(context: Context, storage: SettingsStorage) = SettingsRepository(context,
        object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String = "fixture:$plainText"
            override fun decrypt(cipherText: String): String = cipherText.removePrefix("fixture:")
        }, storage.dataStore).apply { setDefaultPromptProvidersForTest({ "fixture prompt" }, { "fixture dictionary" }) }

    private class FileContext(private val root: File) : ContextWrapper(null) {
        override fun getApplicationContext(): Context = this
        override fun getFilesDir(): File = root
        override fun getPackageName(): String = "dev.clickn.translate.storage.ownedfixture"
    }

    companion object { private const val PATH = "datastore/clickntranslate_settings.preferences_pb" }
}
