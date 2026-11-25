// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class SettingsImportAtomicityAuditTest {

    @Test
    fun bundleImport_stagesEveryFontBeforeAnyPersistentCommit() {
        val viewModel = sourceFile("src/main/java/dev/clickn/translate/ui/SettingsViewModel.kt").readText()
        assertTrue("UI must use the durable importer", viewModel.contains("settingsBundleImporter.import(uri)"))
        val source = sourceFile("src/main/java/dev/clickn/translate/data/SettingsBundleImporter.kt").readText()
        val function = source.substring(
            source.indexOf("internal suspend fun importSource"),
            source.indexOf("private suspend fun recoverLocked"),
        )
        val stage = function.indexOf("stageTransferredFont")
        val fontCommit = function.indexOf("commitTransferredFont")
        val glossaryCommit = function.indexOf("glossary.importTermsForSettingsImport")
        val settingsCommit = function.indexOf("settings.updateImportedSettings(")

        assertTrue("font staging must happen first", stage >= 0)
        assertTrue("font files commit after full package staging", fontCommit > stage)
        assertTrue("glossary commits after fonts are validated", glossaryCommit > fontCommit)
        assertTrue("settings commits only after atomic glossary import", settingsCommit > glossaryCommit)
    }

    @Test
    fun bundleImport_hasCompensatingRollbackForEveryPersistentStore() {
        val coordinator = sourceFile("src/main/java/dev/clickn/translate/data/SettingsBundleImporter.kt").readText()
        val glossary = sourceFile("src/main/java/dev/clickn/translate/glossary/TranslationGlossary.kt").readText()

        listOf(
            "settings.recoverImportedSettings(record.settings)",
            "withContext(NonCancellable)",
            "glossary.importTermsForSettingsImport(",
            "glossary.recoverSettingsImport(record.glossary)",
            "fonts.recoverTransferredFont(it, staging, referenced)",
        ).forEach { marker ->
            assertTrue("missing import rollback: $marker", coordinator.contains(marker))
        }
        assertTrue("glossary import must be a Room transaction", glossary.contains("suspend fun importTermsAtomically"))
        assertTrue("glossary rollback must be a Room transaction", glossary.contains("suspend fun rollbackSettingsImportAtomically"))
        assertTrue("settings rollback must not replace unrelated glossary rows", !coordinator.contains("restoreTerms("))
        assertTrue("durable settings intent must be connected", coordinator.contains("SettingsImportRollback(journal::recordSettings)"))
        assertTrue("durable glossary intent must be connected", coordinator.contains("GlossaryImportRollback(journal::recordGlossary)"))
        assertTrue("Room intent must be persisted before transaction return", glossary.contains("journal?.persistBeforeCommit()"))
    }

    private fun sourceFile(path: String): File = listOf(File(path), File("app", path))
        .firstOrNull(File::isFile)
        ?: error("Source file not found: $path")
}
