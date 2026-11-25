package dev.clickn.translate.glossary

import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Actual Room transactions, including writes made after an import and before its cancellation. */
@RunWith(AndroidJUnit4::class)
class SettingsGlossaryRollbackIntegrationTest {
    @Test fun cancelledImportRetainsLaterEditsAndNewTermsAndReversesRepeatedIds() = runBlocking {
        withRepository { dao, repository ->
            val originals = listOf("Alice", "Bob", "Charlie", "Dora", "Echo").mapIndexed { index, source ->
                term(source, "original-$source").copy(id = index + 1L)
            }
            dao.insertAll(originals)
            val journal = GlossaryImportRollback()
            val committed = CompletableDeferred<Map<String, GlossaryTermEntity>>()
            val importJob = launch {
                try {
                    repository.importTermsForSettingsImport(listOf(
                        term("Alice", "imported-Alice"), term("Charlie", "imported-Charlie"),
                        term("Dora", "imported-Dora"),
                        term("Echo", "imported-Echo-first"), term("Echo", "imported-Echo-second"),
                        term("Foxtrot", "imported-Foxtrot"), term("Golf", "imported-Golf"),
                        term("Hotel", "imported-Hotel-first"), term("Hotel", "imported-Hotel-second"),
                    ), journal)
                    committed.complete(dao.listAll().associateBy { it.sourceTerm })
                    awaitCancellation()
                } finally {
                    withContext(NonCancellable) { repository.rollbackSettingsImport(journal) }
                }
            }
            try {
                val imported = committed.await()
                val lateCharlie = imported.getValue("Charlie").lateEdit("late-overlay-Charlie")
                val lateFoxtrot = imported.getValue("Foxtrot").lateEdit("late-overlay-Foxtrot")
                val lateBob = imported.getValue("Bob").lateEdit("late-overlay-Bob")
                dao.update(lateCharlie)
                dao.update(lateFoxtrot)
                dao.update(lateBob)
                repository.delete(imported.getValue("Dora").id)
                val newId = repository.upsert(term("India", "late-new-term"))
                val lateNew = dao.listAll().single { it.id == newId }
                importJob.cancelAndJoin()

                val actual = dao.listAll().associateBy { it.sourceTerm }
                assertEquals(setOf("Alice", "Bob", "Charlie", "Echo", "Foxtrot", "India"), actual.keys)
                assertEquals(originals.single { it.sourceTerm == "Alice" }, actual["Alice"])
                // Two updates of the same existing ID must unwind in reverse order.
                assertEquals(originals.single { it.sourceTerm == "Echo" }, actual["Echo"])
                assertEquals(lateCharlie, actual["Charlie"])
                assertEquals(lateFoxtrot, actual["Foxtrot"])
                assertEquals(lateBob, actual["Bob"])
                assertEquals(lateNew, actual["India"])
                assertFalse("A deleted imported term must not be resurrected", "Dora" in actual)
                assertFalse("An untouched inserted ID must be removed", "Golf" in actual)
                assertFalse("Repeated changes of a new ID must unwind through insertion", "Hotel" in actual)
                val afterFirstRollback = dao.listAll()
                repository.rollbackSettingsImport(journal)
                assertEquals("Compensation must be idempotent", afterFirstRollback, dao.listAll())
            } finally {
                importJob.cancelAndJoin()
            }
        }
    }

    @Test fun failedRoomTransactionDiscardsItsJournalWithoutTouchingLaterRows() = runBlocking {
        withRepository { dao, repository ->
            val original = term("Alice", "original-Alice").copy(id = 1)
            dao.insert(original)
            val journal = GlossaryImportRollback()
            val failure = runCatching {
                repository.importTermsForSettingsImport(listOf(
                    term("Alice", "must-roll-back"), term("New term", "must-not-exist"),
                    term("Invalid term", " "),
                ), journal)
            }.exceptionOrNull()
            assertTrue("Invalid row must reject the complete transaction", failure is IllegalArgumentException)
            assertEquals(listOf(original), dao.listAll())
            val lateId = repository.upsert(term("New term", "created-after-failure"))
            val late = dao.listAll().single { it.id == lateId }
            repository.rollbackSettingsImport(journal)
            assertEquals(setOf(original, late), dao.listAll().toSet())
        }
    }

    private suspend fun withRepository(
        block: suspend (TranslationGlossaryDao, TranslationGlossaryRepository) -> Unit,
    ) {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val database = Room.inMemoryDatabaseBuilder(context, TranslationGlossaryDatabase::class.java).build()
        try {
            val dao = database.glossaryDao()
            block(dao, TranslationGlossaryRepository(dao))
        } finally {
            database.close()
        }
    }

    private fun term(source: String, target: String) = GlossaryTermEntity(
        sourceLang = "en", targetLang = "ru", sourceTerm = source, targetTerm = target,
        createdAtMs = 10, updatedAtMs = 10,
    )

    private fun GlossaryTermEntity.lateEdit(target: String): GlossaryTermEntity = copy(
        targetTerm = target, updatedAtMs = updatedAtMs + 1_000,
    )
}
