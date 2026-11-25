package dev.clickn.translate.data

import android.content.Context
import android.net.Uri
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.glossary.GlossaryImportRollback
import dev.clickn.translate.glossary.TranslationGlossaryRepository
import java.io.File
import java.io.InputStream
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

internal enum class SettingsImportCheckpoint { FONTS, GLOSSARY, SETTINGS, COMMITTED, UI_PREFERENCES }

/** One local import at a time; unfinished multi-store work is compensated on next startup. */
@Singleton
class SettingsBundleImporter @Inject constructor(
    @ApplicationContext private val context: Context,
    private val settings: SettingsRepository,
    private val glossary: TranslationGlossaryRepository,
    private val fonts: OverlayFontManager,
    private val cipher: SettingsSecretCipher,
    private val recoveryGate: SettingsImportRecoveryGate,
) {
    private val mutex = Mutex()
    private val journalRoot get() = File(context.noBackupFilesDir, SettingsImportJournal.DIRECTORY)
    private fun journal() = SettingsImportJournal(journalRoot, cipher)

    internal suspend fun recoverPendingImport() = withContext(Dispatchers.IO) {
        mutex.withLock { recoverLocked(journal()) }
    }

    suspend fun import(uri: Uri): SettingsBundleImportResult = importSource {
        context.contentResolver.openInputStream(uri) ?: error("Could not open the selected settings file.")
    }

    internal suspend fun importSource(
        checkpoint: suspend (SettingsImportCheckpoint) -> Unit = {},
        open: () -> InputStream,
    ): SettingsBundleImportResult = withContext(Dispatchers.IO) {
        recoveryGate.withReadyLock(mutex) {
            fonts.withImportMutationLock {
                val journal = journal()
                // A previous live rollback may have failed. Never overwrite its only backup.
                recoverLocked(journal)
                val stagingDir = journal.begin()
                try {
                    val importContext = currentCoroutineContext()
                    val stagedFonts = mutableListOf<StagedOverlayFont>()
                    val preview = open().use { source ->
                        SettingsBundleTransfer.read(source, checkpoint = { importContext.ensureActive() }) { font, input ->
                            stagedFonts += fonts.stageTransferredFont(font, input, stagingDir)
                        }
                    }
                    val settingsRollback = SettingsImportRollback(journal::recordSettings)
                    if (preview.legacyPresetOnly) {
                        val presets = settings.importPresetValues(preview.presets, settingsRollback)
                        checkpoint(SettingsImportCheckpoint.SETTINGS)
                        importContext.ensureActive()
                        journal.decide(SettingsImportRecord.COMMITTED)
                        checkpoint(SettingsImportCheckpoint.COMMITTED)
                        journal.cleanTerminal(checkNotNull(journal.read()))
                        return@withImportMutationLock SettingsBundleImportResult(settings.get(), presets.importedCount,
                            presets.overwrittenNames, 0, 0, legacyPresetOnly = true)
                    }

                    journal.recordUiPreferences(UiPreferenceTransfer.plan(context, preview.uiPreferences))
                    val imported = requireNotNull(preview.settings)
                    val before = settings.get()
                    val beforeFontReferences = before.overlayFonts.mapTo(mutableSetOf()) { it.fileName }
                        .apply { add(before.overlayFontFileName) }
                    val committedFonts = stagedFonts.map { staged ->
                        importContext.ensureActive()
                        fonts.commitTransferredFont(staged,
                            { change -> journal.recordFont(change.copy(referencedBefore = change.fileName in beforeFontReferences)) },
                            journal::markFontPublished)
                    }
                    checkpoint(SettingsImportCheckpoint.FONTS)
                    val available = fonts.existingFontEntries(
                        before.overlayFonts + imported.overlayFonts + committedFonts.map { it.entry },
                    )
                    importContext.ensureActive()
                    val glossaryCount = glossary.importTermsForSettingsImport(preview.glossaryTerms,
                        GlossaryImportRollback(journal::recordGlossary))
                    checkpoint(SettingsImportCheckpoint.GLOSSARY)
                    var merged: SettingsBundleMergeResult? = null
                    val result = settings.updateImportedSettings(imported.translationPresets.mapTo(mutableSetOf()) { it.name },
                        settingsRollback) { current ->
                        SettingsBundleTransfer.mergeImportedSettings(current, imported, available,
                            preview.appliedSettingFields).also { merged = it }.settings
                    }
                    checkpoint(SettingsImportCheckpoint.SETTINGS)
                    importContext.ensureActive()
                    // No backup can be removed before this durable decision.
                    journal.decide(SettingsImportRecord.COMMITTED)
                    checkpoint(SettingsImportCheckpoint.COMMITTED)
                    // A locale change recreates the Activity and may cancel its import caller.
                    // Finish the already committed UI choices and journal cleanup on IO anyway.
                    withContext(NonCancellable) {
                        UiPreferenceTransfer.applyCommitted(context, checkNotNull(journal.read()).uiPreferences)
                        checkpoint(SettingsImportCheckpoint.UI_PREFERENCES)
                        journal.cleanTerminal(checkNotNull(journal.read()))
                    }
                    val presets = requireNotNull(merged).presetResult
                    SettingsBundleImportResult(result, presets.importedCount, presets.overwrittenNames,
                        committedFonts.size, glossaryCount, legacyPresetOnly = false,
                        skippedSettingFieldCount = preview.skippedSettingFields.size)
                } catch (error: Throwable) {
                    if (error is Exception) {
                        withContext(NonCancellable) {
                            runCatching { recoverLocked(journal) }.exceptionOrNull()?.let {
                                recoveryGate.requireRecovery()
                                error.addSuppressed(it)
                            }
                        }
                    } else {
                        // A fatal error need not immediately kill every application
                        // coroutine. Retain the durable intent, but close public reads
                        // and new writes until explicit recovery has actually finished.
                        recoveryGate.requireRecovery()
                    }
                    throw error
                }
            }
        }
    }

    private suspend fun recoverLocked(journal: SettingsImportJournal) {
        val record = journal.read() ?: return
        if (record.decision == SettingsImportRecord.PENDING) {
            settings.recoverImportedSettings(record.settings)
            glossary.recoverSettingsImport(record.glossary)
            val referenced = settings.importedFontReferencesForRecovery()
            val staging = journal.directory(record)
            record.fonts.asReversed().forEach { fonts.recoverTransferredFont(it, staging, referenced) }
            journal.decide(SettingsImportRecord.ROLLED_BACK)
        }
        val terminal = checkNotNull(journal.read())
        if (terminal.decision == SettingsImportRecord.COMMITTED) {
            UiPreferenceTransfer.applyCommitted(context, terminal.uiPreferences)
        }
        journal.cleanTerminal(terminal)
    }
}
