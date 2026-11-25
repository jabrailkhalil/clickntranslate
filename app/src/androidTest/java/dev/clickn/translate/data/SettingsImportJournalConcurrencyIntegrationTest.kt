package dev.clickn.translate.data

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.glossary.GlossaryImportRollback
import dev.clickn.translate.glossary.GlossaryTermEntity
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real Android AtomicFile and owned directories; cipher payloads contain synthetic fixtures only. */
@RunWith(AndroidJUnit4::class)
class SettingsImportJournalConcurrencyIntegrationTest {
    @Test fun concurrentCheckpointsFromDifferentInstancesRetainBothStoreIntents() = withOwned { root ->
        val settingsWriter = journal(root)
        settingsWriter.begin()
        val roomWriter = journal(root)
        roomWriter.read()
        val changes = preferenceChanges("imported")
        val term = GlossaryTermEntity(id = 1, sourceLang = "en", targetLang = "ru",
            sourceTerm = "Fixture", targetTerm = "Imported", createdAtMs = 1, updatedAtMs = 1)
        val glossary = listOf(GlossaryImportRollback.Change(null, term))
        val release = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        val callbacks = listOf<() -> Unit>(
            { settingsWriter.recordSettings(changes) },
            { roomWriter.recordGlossary(glossary) },
        ).map { callback -> Thread {
            try { check(release.await(5, TimeUnit.SECONDS)); callback() }
            catch (caught: Throwable) { failure.compareAndSet(null, caught) }
        }.apply { start() } }
        release.countDown()
        callbacks.forEach { it.join(10_000) }
        assertTrue(callbacks.none { it.isAlive })
        assertNull(failure.get())
        val persisted = requireNotNull(journal(root).read())
        assertEquals(changes, persisted.settings)
        assertEquals(glossary, persisted.glossary)
    }

    @Test fun lateCallbackCannotOverwriteTheNextImportAfterOldIntentWasCleaned() = withOwned { root ->
        val stale = journal(root)
        stale.begin()
        stale.recordSettings(preferenceChanges("old import"))
        val cleanup = journal(root)
        cleanup.decide(SettingsImportRecord.ROLLED_BACK)
        cleanup.cleanTerminal(requireNotNull(cleanup.read()))
        val next = journal(root)
        next.begin()
        next.recordSettings(preferenceChanges("next import"))
        val expected = requireNotNull(next.read())

        assertThrows(IllegalStateException::class.java) { stale.recordSettings(preferenceChanges("late old callback")) }

        assertEquals(expected, next.read())
    }

    @Test fun terminalDecisionRejectsLateStoreIntentAndCannotBeChangedToRollback() = withOwned { root ->
        val writer = journal(root)
        writer.begin()
        writer.recordSettings(preferenceChanges("imported"))
        writer.decide(SettingsImportRecord.COMMITTED)
        val committed = requireNotNull(writer.read())

        assertThrows(IllegalStateException::class.java) { writer.recordSettings(preferenceChanges("late")) }
        assertThrows(IllegalStateException::class.java) { writer.decide(SettingsImportRecord.ROLLED_BACK) }

        assertEquals(committed, writer.read())
    }

    @Test fun directorySyncFailureAfterFinishKeepsThePublishedIntentAndItsBackups() = withOwned { root ->
        var rejectSync = false
        val writer = SettingsImportJournal(root, fixtureCipher) { directory ->
            if (rejectSync) throw IOException("owned synthetic directory sync failure")
            SettingsImportJournal.syncDirectory(directory)
        }
        val staging = writer.begin()
        val backup = File(staging, "retained-backup").apply { writeText("original owned bytes") }
        rejectSync = true

        assertThrows(IOException::class.java) { writer.recordSettings(preferenceChanges("imported")) }

        assertTrue(File(root, "active.enc").isFile)
        assertEquals("original owned bytes", backup.readText())
        assertEquals(preferenceChanges("imported"), requireNotNull(journal(root).read()).settings)
        rejectSync = false
        writer.decide(SettingsImportRecord.ROLLED_BACK)
        writer.cleanTerminal(requireNotNull(writer.read()))
        assertNull(journal(root).read())
    }

    private fun journal(root: File) = SettingsImportJournal(root, fixtureCipher)

    private fun preferenceChanges(after: String) = listOf(ImportPreferenceChange(
        "owned_fixture_preference", ImportPreferenceValues.encode("original"), ImportPreferenceValues.encode(after),
    ))

    private fun withOwned(action: (File) -> Unit) {
        val cache = InstrumentationRegistry.getInstrumentation().targetContext.cacheDir
        val root = Files.createTempDirectory(cache.toPath(), "import-journal-concurrency-").toFile()
        try { action(root) }
        finally {
            check(root.canonicalFile.parentFile == cache.canonicalFile)
            check(root.deleteRecursively())
        }
    }

    private val fixtureCipher = object : SettingsSecretCipher {
        // Encoding fixture, not a replacement for the production authenticated cipher.
        override fun encrypt(plainText: String): String = Base64.getEncoder().encodeToString(plainText.toByteArray())
        override fun decrypt(cipherText: String): String = Base64.getDecoder().decode(cipherText).toString(Charsets.UTF_8)
    }
}
