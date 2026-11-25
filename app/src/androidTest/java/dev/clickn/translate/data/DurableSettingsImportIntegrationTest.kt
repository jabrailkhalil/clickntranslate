package dev.clickn.translate.data

import android.content.Context
import android.content.ContextWrapper
import android.content.SharedPreferences
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.room.Room
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.glossary.GlossaryTermEntity
import dev.clickn.translate.glossary.TranslationGlossaryDatabase
import dev.clickn.translate.glossary.TranslationGlossaryRepository
import dev.clickn.translate.ui.theme.ThemeAccent
import dev.clickn.translate.ui.theme.ThemeAccentPrefs
import dev.clickn.translate.ui.theme.ThemeMode
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.file.Files
import java.security.MessageDigest
import java.util.Base64
import java.util.concurrent.ConcurrentHashMap
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real AtomicFile, file-backed DataStore and Room, reopened across simulated fatal process exits. */
@RunWith(AndroidJUnit4::class)
class DurableSettingsImportIntegrationTest {
    @Test fun deathAfterFontPublicationRestoresOriginalAndRemovesNewFont() = runBlocking {
        crashAndRecover(SettingsImportCheckpoint.FONTS)
    }
    @Test fun deathAfterRoomCommitRecoversBeforeFirstPublicRead() = runBlocking {
        crashAndRecover(SettingsImportCheckpoint.GLOSSARY)
    }
    @Test fun deathAfterDataStoreCommitRestoresLocalCredentialsAndAllStores() = runBlocking {
        crashAndRecover(SettingsImportCheckpoint.SETTINGS)
    }
    @Test fun deathAfterCommitDecisionPreservesWholeImportAndOnlyCleansStaging() = runBlocking {
        crashAndRecover(SettingsImportCheckpoint.COMMITTED)
    }

    @Test fun successfulImportPersistsInterfaceChoicesTogetherWithProfilesTermsAndFonts() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.session.importer.importSource { fixture.bundle.inputStream() }
            fixture.assertCommitted()
            assertNull(fixture.journal().read())
            fixture.reopen(autoRecover = true)
            fixture.assertCommitted()
        }
    }

    @Test fun deathAfterInterfacePublicationReplaysWithoutIncrementingChoiceRevisions() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.crashAt(SettingsImportCheckpoint.UI_PREFERENCES)
            assertEquals(SettingsImportRecord.COMMITTED, fixture.journal().read()?.decision)
            fixture.assertUi(fixture.importedUi)
            val publishedRevisions = fixture.uiRevisions()
            fixture.reopenAndRecover()
            fixture.assertCommitted()
            assertEquals(publishedRevisions, fixture.uiRevisions())
            fixture.session.importer.recoverPendingImport()
            assertEquals(publishedRevisions, fixture.uiRevisions())
            assertNull(fixture.journal().read())
        }
    }

    @Test fun committedRecoveryKeepsInterfaceChoicesMadeAfterTheImportDecision() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.crashAt(SettingsImportCheckpoint.COMMITTED)
            fixture.writeUi(fixture.laterUi)
            val laterRevisions = fixture.uiRevisions()
            fixture.reopenAndRecover()
            fixture.assertCommitted(expectedUi = fixture.laterUi)
            assertEquals(laterRevisions, fixture.uiRevisions())
            assertNull(fixture.journal().read())
        }
    }

    @Test fun committedRecoveryDoesNotOverwriteInterfaceChoicesChangedAndRevertedLater() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.crashAt(SettingsImportCheckpoint.COMMITTED)
            fixture.writeUi(fixture.laterUi)
            fixture.writeUi(fixture.originalUi)
            val revertedRevisions = fixture.uiRevisions()
            fixture.reopenAndRecover()
            fixture.assertCommitted(expectedUi = fixture.originalUi)
            assertEquals(revertedRevisions, fixture.uiRevisions())
            assertNull(fixture.journal().read())
        }
    }

    @Test fun rollbackDoesNotKeepANewFontMerelyBecauseAnOldMissingFileWasReferenced() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.session.settings.update { it.copy(overlayFontFileName = fixture.fontNames.last(),
                overlayFontDisplayName = "Old missing file", overlayFonts = listOf(OverlayFontEntry(fixture.fontNames.last(), "Old missing file"))) }
            fixture.original = fixture.session.settings.get()
            fixture.crashAt(SettingsImportCheckpoint.SETTINGS)
            fixture.reopenAndRecover()
            fixture.assertOriginal()
        }
    }

    @Test fun cancellationAfterRoomCommitCompensatesBeforeReturningCancellation() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            val committed = CompletableDeferred<Unit>()
            val importing = launch(Dispatchers.IO) {
                fixture.session.importer.importSource(checkpoint = {
                    if (it == SettingsImportCheckpoint.GLOSSARY) { committed.complete(Unit); awaitCancellation() }
                }) { fixture.bundle.inputStream() }
            }
            try {
                withTimeout(5_000) { committed.await() }
                importing.cancelAndJoin()
                assertTrue(importing.isCancelled)
            } finally { importing.cancelAndJoin() }
            fixture.assertOriginal()
            assertNull(fixture.journal().read())
        }
    }

    @Test fun recoveryRetainsLaterSettingsAndGlossaryEditsAndDoesNotResurrectDeletion() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            val failure = runCatching {
                fixture.session.importer.importSource(checkpoint = { stage ->
                    if (stage == SettingsImportCheckpoint.SETTINGS) {
                        fixture.session.settings.update { it.copy(overlayAlpha = 0.42f) }
                        val rows = fixture.session.glossary.listAll()
                        fixture.session.glossary.upsert(rows.single { it.sourceTerm == "Alice" }.copy(
                            targetTerm = "later user edit", updatedAtMs = Long.MAX_VALUE - 1))
                        fixture.session.glossary.delete(rows.single { it.sourceTerm == "Beta" }.id)
                        fixture.session.glossary.upsert(term("Charlie", "later new row"))
                        throw SimulatedProcessDeath()
                    }
                }) { fixture.bundle.inputStream() }
            }.exceptionOrNull()
            assertTrue(failure is SimulatedProcessDeath)
            fixture.reopenAndRecover()
            assertEquals("ru", fixture.session.settings.get().targetLang)
            assertEquals(0.42f, fixture.session.settings.get().overlayAlpha)
            val rows = fixture.session.glossary.listAll().associateBy { it.sourceTerm }
            assertEquals(setOf("Alice", "Charlie"), rows.keys)
            assertEquals("later user edit", rows.getValue("Alice").targetTerm)
            assertEquals("later new row", rows.getValue("Charlie").targetTerm)
            assertEquals(LOCAL_SECRET, fixture.session.settings.settingsForSnapshot(fixture.originalPreset).apiKey)
            fixture.session.importer.recoverPendingImport()
            assertEquals(rows, fixture.session.glossary.listAll().associateBy { it.sourceTerm })
        }
    }

    @Test fun unreadableEncryptedJournalExposesNoPartialStateAndCanRetryAfterRepair() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.crashAt(SettingsImportCheckpoint.SETTINGS)
            val file = File(fixture.journalRoot, "active.enc")
            val intact = file.readBytes()
            assertFalse(intact.toString(Charsets.UTF_8).contains(LOCAL_SECRET))
            file.writeText("invalid encrypted fixture")
            fixture.reopen(autoRecover = false)
            val read = async(start = CoroutineStart.UNDISPATCHED) { fixture.session.settings.get() }
            try {
                fixture.session.startRecovery()
                withTimeout(5_000) { fixture.session.gate.state.first { it == SettingsImportRecoveryState.FAILED } }
                assertNull(withTimeoutOrNull(100) { read.await(); Unit })
                assertNull(fixture.session.fonts.typefaceFor(fixture.fontNames.last()))
                assertEquals("invalid encrypted fixture", file.readText())
                file.writeBytes(intact)
                fixture.session.gate.retry()
                withTimeout(5_000) { read.await() }
            } finally { read.cancelAndJoin() }
            fixture.assertOriginal()
        }
    }

    @Test fun encryptionFailureBeforeIntentNeverChangesAnyStore() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.cipher.failEncryption = true
            assertTrue(runCatching { fixture.session.importer.importSource { fixture.bundle.inputStream() } }.isFailure)
            fixture.cipher.failEncryption = false
            fixture.assertOriginal()
            assertNull(fixture.journal().read())
        }
    }

    @Test fun cleanupFailureAfterCommittedDecisionNeverRollsBackCommittedData() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            val outside = File(fixture.root, "retained-outside-import.txt").apply { writeText("owned retained fixture") }
            var link: File? = null
            val failure = runCatching {
                fixture.session.importer.importSource(checkpoint = { stage ->
                    if (stage == SettingsImportCheckpoint.COMMITTED) {
                        val record = checkNotNull(fixture.journal().read())
                        link = File(fixture.journal().directory(record), "unexpected-link")
                        Files.createSymbolicLink(checkNotNull(link).toPath(), outside.toPath())
                    }
                }) { fixture.bundle.inputStream() }
            }.exceptionOrNull()
            assertTrue(failure is IllegalStateException)
            assertEquals(SettingsImportRecoveryState.FAILED, fixture.session.gate.state.value)
            assertEquals(SettingsImportRecord.COMMITTED, fixture.journal().read()?.decision)
            assertEquals("owned retained fixture", outside.readText())
            Files.delete(checkNotNull(link).toPath())
            fixture.session.gate.retry()
            withTimeout(5_000) { fixture.session.gate.awaitReady() }
            fixture.assertCommitted()
            assertEquals("owned retained fixture", outside.readText())
            assertNull(fixture.journal().read())
        }
    }

    @Test fun interruptedUnpublishedFirstIntentHasNoStoreEffectsAndDoesNotBlockStartup() = runBlocking {
        withOwned { fixture ->
            fixture.seed()
            fixture.journalRoot.mkdirs()
            File(fixture.journalRoot, "active.enc.new").writeText("partial first write")
            fixture.reopenAndRecover()
            fixture.assertOriginal()
            assertFalse(File(fixture.journalRoot, "active.enc.new").exists())
        }
    }

    private suspend fun crashAndRecover(point: SettingsImportCheckpoint) = withOwned { fixture ->
        fixture.seed()
        fixture.crashAt(point)
        val pending = checkNotNull(fixture.journal().read())
        assertEquals(if (point == SettingsImportCheckpoint.COMMITTED) SettingsImportRecord.COMMITTED else SettingsImportRecord.PENDING,
            pending.decision)
        // UI choices are published only after the durable decision. A crash at the
        // COMMITTED hook still has the local appearance until startup rolls forward.
        fixture.assertUi(fixture.originalUi)
        assertFalse(File(fixture.journalRoot, "active.enc").readText().contains(LOCAL_SECRET))
        fixture.reopenAndRecover()
        if (point == SettingsImportCheckpoint.COMMITTED) fixture.assertCommitted() else fixture.assertOriginal()
        fixture.session.importer.recoverPendingImport()
        if (point == SettingsImportCheckpoint.COMMITTED) fixture.assertCommitted() else fixture.assertOriginal()
        assertNull(fixture.journal().read())
    }

    private suspend fun withOwned(action: suspend (Fixture) -> Unit) {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        val root = Files.createTempDirectory(app.cacheDir.toPath(), "durable-settings-import-test-").toFile()
        val fixture = Fixture(app, root)
        try { withTimeout(30_000) { action(fixture) } }
        finally { fixture.close(); check(root.canonicalFile.parentFile == app.cacheDir.canonicalFile); root.deleteRecursively() }
    }

    private class SimulatedProcessDeath : Error("simulated fatal process exit")

    private class Fixture(private val app: Context, val root: File) {
        private val preferencePrefix = "${root.name}-"
        private val ownedPreferenceNames = ConcurrentHashMap.newKeySet<String>()
        val context = object : ContextWrapper(app) {
            override fun getApplicationContext(): Context = this
            override fun getFilesDir(): File = File(root, "files").apply { mkdirs() }
            override fun getNoBackupFilesDir(): File = File(root, "no-backup").apply { mkdirs() }
            override fun getCacheDir(): File = File(root, "cache").apply { mkdirs() }
            override fun getDatabasePath(name: String): File = File(root, "databases/$name").apply { parentFile?.mkdirs() }
            override fun getSharedPreferences(name: String, mode: Int): SharedPreferences {
                val ownedName = preferencePrefix + name
                ownedPreferenceNames += ownedName
                return app.getSharedPreferences(ownedName, mode)
            }
        }
        val cipher = FixtureCipher()
        val journalRoot get() = File(context.noBackupFilesDir, SettingsImportJournal.DIRECTORY)
        var session = Session(context, cipher)
        lateinit var original: Settings
        lateinit var originalPreset: TranslationPreset
        lateinit var bundle: ByteArray
        lateinit var fontNames: List<String>
        private lateinit var fontBytes: List<ByteArray>
        private val originalFontBytes = "owned invalid original font".toByteArray()
        private val originalTerm = term("Alice", "original term").copy(id = 10, createdAtMs = 10, updatedAtMs = 10)
        val originalUi = PortableUiPreferences(ThemeMode.LIGHT, ThemeAccent.LAVENDER.name, "en", "chester")
        val importedUi = PortableUiPreferences(ThemeMode.AMOLED, ThemeAccent.OCEAN.name, "ru", "doc")
        val laterUi = PortableUiPreferences(ThemeMode.DARK, ThemeAccent.MINT.name, "fr", "pancake")

        fun journal() = SettingsImportJournal(journalRoot, cipher)
        private fun font(name: String) = File(context.filesDir, "${OverlayFontPolicy.FONT_DIR_NAME}/$name")

        suspend fun seed() {
            writeUi(originalUi)
            fontBytes = File("/system/fonts").listFiles().orEmpty()
                .filter { it.isFile && it.extension == "ttf" && it.length() in 1..(5L * 1024 * 1024) }
                .sortedBy { it.name }.asSequence().map { it.readBytes() }.distinctBy(::sha256).take(2).toList()
            check(fontBytes.size == 2) { "Test requires two installed system TrueType fonts." }
            fontNames = fontBytes.map { OverlayFontPolicy.storedFileNameForSha256(sha256(it)) }
            font(fontNames.first()).apply { parentFile?.mkdirs(); writeBytes(originalFontBytes) }
            val local = Settings(sourceLang = "en", targetLang = "ru", translatorEngine = TranslatorEngine.OPENAI,
                apiKey = LOCAL_SECRET, model = "fixture-original")
            session.settings.update { local }
            originalPreset = TranslationPresetCatalog.fromSettings("custom_fixture", "Fixture profile", "F", local)
            session.settings.saveTranslationPreset(originalPreset, local)
            original = session.settings.get()
            session.database.glossaryDao().insert(originalTerm)
            val remote = local.copy(targetLang = "ar", overlayFontFileName = fontNames.last(),
                overlayFontDisplayName = "Fixture two", overlayFonts = fontNames.mapIndexed { index, name ->
                    OverlayFontEntry(name, "Fixture $index")
                })
            val importedPreset = TranslationPresetCatalog.fromSettings("custom_remote", "Fixture profile", "F", remote)
            val sources = fontNames.zip(fontBytes).associate { (name, bytes) ->
                name to File(root, "source-$name").apply { writeBytes(bytes) }
            }
            bundle = ByteArrayOutputStream().also { output ->
                SettingsBundleTransfer.write(output, remote.copy(translationPresets = listOf(importedPreset),
                    activeTranslationPresetId = importedPreset.id), listOf(term("Alice", "imported term"), term("Beta", "new term")),
                    uiPreferences = importedUi) { sources[it] }
            }.toByteArray()
        }

        suspend fun crashAt(point: SettingsImportCheckpoint) {
            val failure = runCatching {
                session.importer.importSource(checkpoint = { if (it == point) throw SimulatedProcessDeath() }) { bundle.inputStream() }
            }.exceptionOrNull()
            assertTrue("Crash checkpoint must actually be reached", failure is SimulatedProcessDeath)
            assertEquals("A surviving process must not expose unfinished import state",
                SettingsImportRecoveryState.FAILED, session.gate.state.value)
        }

        suspend fun reopen(autoRecover: Boolean = false) {
            session.close()
            session = Session(context, cipher)
            if (autoRecover) { session.startRecovery(); withTimeout(5_000) { session.gate.awaitReady() } }
        }

        suspend fun reopenAndRecover() = coroutineScope {
            reopen()
            val waiting = async(Dispatchers.IO, start = CoroutineStart.UNDISPATCHED) { session.settings.get() }
            try {
                assertNull(withTimeoutOrNull(100) { waiting.await(); Unit })
                session.startRecovery()
                withTimeout(5_000) { waiting.await() }
            } finally { waiting.cancelAndJoin() }
        }

        suspend fun assertOriginal() {
            assertUi(originalUi)
            assertEquals(original, session.settings.get())
            assertEquals(listOf(originalTerm), session.glossary.listAll())
            assertArrayEquals(originalFontBytes, font(fontNames.first()).readBytes())
            assertFalse(font(fontNames.last()).exists())
            assertEquals(LOCAL_SECRET, session.settings.settingsForSnapshot(originalPreset).apiKey)
        }

        suspend fun assertCommitted(expectedUi: PortableUiPreferences = importedUi) {
            assertUi(expectedUi)
            assertEquals("ar", session.settings.get().targetLang)
            val rows = session.glossary.listAll().associateBy { it.sourceTerm }
            assertEquals(setOf("Alice", "Beta"), rows.keys)
            assertEquals("imported term", rows.getValue("Alice").targetTerm)
            fontNames.zip(fontBytes).forEach { (name, bytes) -> assertArrayEquals(bytes, font(name).readBytes()) }
        }

        fun writeUi(values: PortableUiPreferences) {
            ThemeModePrefs.write(context, requireNotNull(values.themeMode))
            ThemeAccentPrefs.write(context, ThemeAccent.valueOf(requireNotNull(values.accent)))
            AppLocalePrefs.write(context, requireNotNull(values.languageTag))
            CompanionPrefs.write(context, requireNotNull(values.companion))
        }

        fun assertUi(expected: PortableUiPreferences) {
            assertEquals(expected.themeMode, ThemeModePrefs.read(context))
            assertEquals(expected.accent, ThemeAccentPrefs.read(context).name)
            assertEquals(expected.languageTag, AppLocalePrefs.read(context))
            assertEquals(expected.companion, CompanionPrefs.read(context))
        }

        fun uiRevisions(): Map<UiPreferenceField, Long> = UiPreferenceField.entries.associateWith { field ->
            field.prefs(context).getLong(field.revisionKey, 0)
        }

        suspend fun close() {
            session.close()
            ownedPreferenceNames.forEach { name ->
                check(name.startsWith(preferencePrefix))
                // Flush queued apply writes before deleting only this fixture's files.
                check(app.getSharedPreferences(name, Context.MODE_PRIVATE).edit().commit())
                check(app.deleteSharedPreferences(name))
            }
        }
    }

    private class Session(context: Context, cipher: SettingsSecretCipher) {
        private val job = SupervisorJob()
        private val scope = CoroutineScope(job + Dispatchers.IO)
        val gate = SettingsImportRecoveryGate(context)
        private val store = PreferenceDataStoreFactory.create(scope = scope) { File(context.filesDir, "test-settings.preferences_pb") }
        val settings = SettingsRepository(context, cipher, store, gate).apply {
            setDefaultPromptProvidersForTest({ "fixture prompt" }, { "fixture dictionary" })
        }
        val database = Room.databaseBuilder(context, TranslationGlossaryDatabase::class.java, "test-glossary.db").build()
        val glossary = TranslationGlossaryRepository(database.glossaryDao(), recoveryGate = gate)
        val fonts = OverlayFontManager(context, settings)
        val importer = SettingsBundleImporter(context, settings, glossary, fonts, cipher, gate)
        init { if (gate.isReady()) startRecovery() }
        fun startRecovery() = gate.start(scope, importer::recoverPendingImport)
        suspend fun close() { job.cancelAndJoin(); database.close() }
    }

    private class FixtureCipher : SettingsSecretCipher {
        private val key = KeyGenerator.getInstance("AES").apply { init(256) }.generateKey()
        var failEncryption = false
        override fun encrypt(plainText: String): String {
            check(!failEncryption) { "Fixture encryption unavailable" }
            val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply { init(Cipher.ENCRYPT_MODE, key) }
            return Base64.getEncoder().encodeToString(cipher.iv + cipher.doFinal(plainText.toByteArray()))
        }
        override fun decrypt(cipherText: String): String {
            val bytes = Base64.getDecoder().decode(cipherText)
            return Cipher.getInstance("AES/GCM/NoPadding").run {
                init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, bytes.copyOfRange(0, 12)))
                doFinal(bytes, 12, bytes.size - 12).toString(Charsets.UTF_8)
            }
        }
    }

    companion object {
        private const val LOCAL_SECRET = "synthetic-fixture-local-credential"
        private fun term(source: String, target: String) = GlossaryTermEntity(sourceLang = "en", targetLang = "ru",
            sourceTerm = source, targetTerm = target, createdAtMs = 10, updatedAtMs = 10)
        private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it) }
    }
}
