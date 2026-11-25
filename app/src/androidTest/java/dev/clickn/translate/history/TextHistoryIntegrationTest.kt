package dev.clickn.translate.history

import android.content.Context
import android.os.Looper
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.IOException
import java.util.UUID
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real, isolated Room files and legacy preferences; never edits the user's history or settings. */
@RunWith(AndroidJUnit4::class)
class TextHistoryIntegrationTest {
    private val context = InstrumentationRegistry.getInstrumentation().targetContext

    @Test fun importsAllLegacyFieldsWithoutTruncationAndReopensWithoutReimporting() = runBlocking {
        withStore { store ->
            val originals = (1..61).map { number -> entry(number.toLong()).copy(
                source = "مرحبا بالعالم\nEnglish paragraph $number",
                translated = "Переведённый абзац $number\n第二段",
                from = "auto", to = "ru", provider = "FUTURE_PROVIDER",
            ) }
            val raw = legacyJson(originals)
            val preferences = context.getSharedPreferences(store.name, Context.MODE_PRIVATE)
            assertTrue(preferences.edit().putString("entries", raw).putString("unrelated", "keep").commit())
            val source = SharedPreferencesTextHistorySource(context, store.name)
            val repository = TextHistoryRepository(store.database, source)
            val imported = repository.observe().first()
            assertNull(imported.issue)
            assertFalse(imported.loading)
            assertEquals(originals.sortedByDescending { it.createdAtMs }.map { it.copy(id = 0) },
                imported.entries.map { it.copy(id = 0) })
            assertEquals(61, imported.entries.map { it.id }.toSet().size)
            assertEquals("Import must preserve the legacy backup byte for byte", raw, preferences.getString("entries", null))
            assertTrue(requireNotNull(store.database.historyDao().state()).legacyImported)

            store.reopen()
            val reopened = TextHistoryRepository(store.database, object : LegacyTextHistorySource {
                override suspend fun read(): String = error("Successful imports must not read the old source again")
                override suspend fun erase() = error("Import does not erase the backup")
            }).observe().first()
            assertEquals(imported.entries, reopened.entries)
            assertEquals("keep", preferences.getString("unrelated", null))
        }
    }

    @Test fun malformedLegacyRemainsRecoverableAndDoesNotBlockNewRoomHistory() = runBlocking {
        withStore { store ->
            val old = listOf(entry(100), entry(101))
            val legacy = MemoryLegacy(legacyJson(old).dropLast(1) + ",null]")
            val repository = TextHistoryRepository(store.database, legacy)
            val failed = repository.observe().first()
            assertEquals(TextHistoryIssue.LEGACY_IMPORT, failed.issue)
            assertTrue(failed.entries.isEmpty())
            assertNull(store.database.historyDao().state())
            assertTrue(repository.save(entry(999), repository.writeGeneration()))
            val originalBytes = legacy.raw
            assertEquals(1, repository.observe().first().entries.size)
            assertEquals(originalBytes, legacy.raw)

            legacy.raw = legacyJson(old)
            val repaired = repository.observe().first()
            assertNull(repaired.issue)
            assertEquals(listOf(999L, 101L, 100L), repaired.entries.map { it.createdAtMs })
            assertEquals(3, TextHistoryRepository(store.database, legacy).observe().first().entries.size)
            assertEquals(0, legacy.erases)
        }
    }

    @Test fun failedInsertRollsBackEveryImportedRowAndTheReceipt() = runBlocking {
        withStore { store ->
            val legacy = MemoryLegacy(legacyJson(listOf(entry(3), entry(2).copy(source = "reject"), entry(1))))
            store.database.openHelper.writableDatabase.execSQL(
                "CREATE TRIGGER reject_owned_fixture BEFORE INSERT ON text_history " +
                    "WHEN NEW.source = 'reject' BEGIN SELECT RAISE(ABORT, 'owned failure'); END",
            )
            val repository = TextHistoryRepository(store.database, legacy)
            try { repository.writeGeneration(); fail("Expected the actual SQLite transaction to fail") }
            catch (_: android.database.sqlite.SQLiteException) { }
            assertTrue(store.database.historyDao().listAll().isEmpty())
            assertNull(store.database.historyDao().state())
            store.database.openHelper.writableDatabase.execSQL("DROP TRIGGER reject_owned_fixture")
            assertEquals(3, repository.observe().first().entries.size)
            assertTrue(requireNotNull(store.database.historyDao().state()).legacyImported)
        }
    }

    @Test fun concurrentRepositoriesImportOnceEvenWithEqualLegacyTimestamps() = runBlocking {
        withStore { store ->
            val legacy = MemoryLegacy(legacyJson(listOf(entry(20).copy(source = "second"), entry(20).copy(source = "first"))))
            val first = TextHistoryRepository(store.database, legacy)
            val second = TextHistoryRepository(store.database, legacy)
            withTimeout(5_000) {
                val a = async { first.writeGeneration() }
                val b = async { second.writeGeneration() }
                assertEquals(0L, a.await())
                assertEquals(0L, b.await())
            }
            val entries = store.database.historyDao().listAll()
            assertEquals(listOf("second", "first"), entries.map { it.source })
            assertEquals(2, entries.map { it.id }.toSet().size)
        }
    }

    @Test fun clearWinsAgainstAnImportAlreadyReadingItsOldSnapshot() = runBlocking {
        withStore { store ->
            val legacy = MemoryLegacy(legacyJson(listOf(entry(10))))
            val readStarted = CompletableDeferred<Unit>()
            val continueRead = CompletableDeferred<Unit>()
            val source = object : LegacyTextHistorySource {
                override suspend fun read(): String {
                    val snapshot = legacy.raw
                    readStarted.complete(Unit)
                    continueRead.await()
                    return snapshot
                }
                override suspend fun erase() = legacy.erase()
            }
            val repository = TextHistoryRepository(store.database, source)
            withTimeout(5_000) {
                val import = async { repository.writeGeneration() }
                readStarted.await()
                repository.clear()
                continueRead.complete(Unit)
                assertEquals(1L, import.await())
            }
            assertTrue(store.database.historyDao().listAll().isEmpty())
            assertEquals("[]", legacy.raw)
            assertTrue(requireNotNull(store.database.historyDao().state()).legacyImported)
            store.reopen()
            assertTrue(TextHistoryRepository(store.database, legacy).observe().first().entries.isEmpty())
        }
    }

    @Test fun clearRejectsResultsFromBeforeClearAndNewResultsKeepTheirLanguageAndProviderScope() = runBlocking {
        withStore { store ->
            val repository = TextHistoryRepository(store.database, MemoryLegacy("[]"))
            val oldGeneration = repository.writeGeneration()
            assertTrue(repository.save(entry(1), oldGeneration))
            repository.clear()
            assertFalse(repository.save(entry(2), oldGeneration))
            store.reopen()
            val reopened = TextHistoryRepository(store.database, MemoryLegacy("[]"))
            assertFalse(reopened.save(entry(3), oldGeneration))
            val current = reopened.writeGeneration()
            val original = entry(10).copy(source = "same input")
            assertTrue(reopened.save(original, current))
            assertTrue(reopened.save(original.copy(createdAtMs = 11, translated = "latest"), current))
            assertTrue(reopened.save(original.copy(createdAtMs = 12, provider = "OTHER"), current))
            assertTrue(reopened.save(original.copy(createdAtMs = 13, to = "de"), current))
            val entries = reopened.observe().first().entries
            assertEquals(3, entries.size)
            assertEquals(listOf(13L, 12L, 11L), entries.map { it.createdAtMs })
            assertEquals("latest", entries.last().translated)
        }
    }

    @Test fun interruptedClearFinishesLegacyErasureAfterReopenWithoutResurrectingRows() = runBlocking {
        withStore { store ->
            val legacy = MemoryLegacy(legacyJson(listOf(entry(10))))
            val erasing = CompletableDeferred<Unit>()
            val repository = TextHistoryRepository(store.database, object : LegacyTextHistorySource {
                override suspend fun read() = legacy.read()
                override suspend fun erase() { erasing.complete(Unit); awaitCancellation() }
            })
            assertEquals(1, repository.observe().first().entries.size)
            val clear = launch { repository.clear() }
            try {
                withTimeout(5_000) { erasing.await() }
            } finally { clear.cancelAndJoin() }
            assertTrue(store.database.historyDao().listAll().isEmpty())
            assertTrue(requireNotNull(store.database.historyDao().state()).legacyErasePending)
            assertNotEquals("[]", legacy.raw)
            store.reopen()
            val reopened = TextHistoryRepository(store.database, legacy).observe().first()
            assertNull(reopened.issue)
            assertTrue(reopened.entries.isEmpty())
            assertEquals("[]", legacy.raw)
            assertFalse(requireNotNull(store.database.historyDao().state()).legacyErasePending)
        }
    }

    @Test fun failedLegacyEraseIsVisibleAndRetriedWithoutDeletingUnrelatedPreferences() = runBlocking {
        withStore { store ->
            val preferences = context.getSharedPreferences(store.name, Context.MODE_PRIVATE)
            val raw = legacyJson(listOf(entry(1)))
            assertTrue(preferences.edit().putString("entries", raw).putBoolean("unrelated", true).commit())
            val source = SharedPreferencesTextHistorySource(context, store.name)
            val repository = TextHistoryRepository(store.database, object : LegacyTextHistorySource {
                override suspend fun read() = source.read()
                override suspend fun erase() { throw IOException("owned failure") }
            })
            repository.writeGeneration()
            repository.clear()
            assertEquals(TextHistoryIssue.LEGACY_ERASE, repository.observe().first().issue)
            assertEquals(raw, preferences.getString("entries", null))
            assertTrue(requireNotNull(store.database.historyDao().state()).legacyErasePending)
            store.reopen()
            assertNull(TextHistoryRepository(store.database, source).observe().first().issue)
            assertFalse(preferences.contains("entries"))
            assertTrue(preferences.getBoolean("unrelated", false))
        }
    }

    @Test fun lateEraseFailureCannotOverrideAnotherSuccessfulClear() = runBlocking {
        withStore { store ->
            val legacy = MemoryLegacy(legacyJson(listOf(entry(1))))
            val erasing = CompletableDeferred<Unit>()
            val continueErase = CompletableDeferred<Unit>()
            val late = TextHistoryRepository(store.database, object : LegacyTextHistorySource {
                override suspend fun read() = legacy.read()
                override suspend fun erase() {
                    erasing.complete(Unit)
                    continueErase.await()
                    throw IOException("owned delayed failure")
                }
            })
            late.writeGeneration()
            withTimeout(5_000) {
                val clear = async { late.clear() }
                erasing.await()
                TextHistoryRepository(store.database, legacy).clear()
                continueErase.complete(Unit)
                clear.await()
            }
            val snapshot = late.observe().first()
            assertNull(snapshot.issue)
            assertTrue(snapshot.entries.isEmpty())
            assertFalse(requireNotNull(store.database.historyDao().state()).legacyErasePending)
        }
    }

    @Test fun initializationAndExplicitClearNeverReadOrWriteLegacyPreferencesOnMain() = runBlocking {
        withStore { store ->
            val legacy = MemoryLegacy(legacyJson(listOf(entry(1))))
            val source = object : LegacyTextHistorySource {
                override suspend fun read(): String {
                    assertNotSame(Looper.getMainLooper(), Looper.myLooper())
                    return legacy.read()
                }
                override suspend fun erase() {
                    assertNotSame(Looper.getMainLooper(), Looper.myLooper())
                    legacy.erase()
                }
            }
            val repository = TextHistoryRepository(store.database, source)
            withContext(Dispatchers.Main) {
                assertEquals(1, repository.observe().first().entries.size)
                repository.clear()
            }
            assertEquals(1, legacy.erases)
        }
    }

    private fun entry(timestamp: Long) = TextHistoryEntry(createdAtMs = timestamp,
        source = "owned source $timestamp", translated = "owned result $timestamp", from = "en", to = "ru", provider = "GOOGLE_ML_KIT")

    private fun legacyJson(entries: List<TextHistoryEntry>): String = buildJsonArray {
        entries.forEach { entry -> add(buildJsonObject {
            put("id", entry.createdAtMs); put("source", entry.source); put("translated", entry.translated)
            put("from", entry.from); put("to", entry.to); put("provider", entry.provider)
            put("futureField", "ignored")
        }) }
    }.toString()

    private class MemoryLegacy(var raw: String) : LegacyTextHistorySource {
        var erases = 0
        override suspend fun read() = raw
        override suspend fun erase() { erases++; raw = "[]" }
    }

    private inner class Store(val name: String) {
        var database: TextHistoryDatabase = open()
            private set
        private fun open() = Room.databaseBuilder(context, TextHistoryDatabase::class.java, "$name.db").build()
        fun reopen() { database.close(); database = open() }
        fun close() {
            database.close()
            context.deleteDatabase("$name.db")
            context.deleteSharedPreferences(name)
        }
    }

    private suspend fun withStore(body: suspend (Store) -> Unit) {
        val store = Store("owned-history-${UUID.randomUUID()}")
        try { body(store) } finally { store.close() }
    }
}
