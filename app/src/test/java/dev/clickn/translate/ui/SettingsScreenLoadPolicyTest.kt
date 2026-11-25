// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.data.Settings
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

class SettingsScreenLoadPolicyTest {
    @Test fun retainedEditRestoresWithoutAnIoReadAndKeepsTheOriginalDirtyBaseline() = runBlocking {
        val persisted = Settings(renderMode = dev.clickn.translate.data.RenderMode.BLOCKS, apiKey = "owned-memory-key")
        val draft = persisted.copy(renderMode = dev.clickn.translate.data.RenderMode.FLOATING_WINDOW,
            apiKey = "owned-unsaved-key", floatingButtonAlpha = 0.6f)
        val restored = loadSettingsEditingSnapshot(SettingsEditingSnapshot(persisted, draft)) {
            error("Restoring an existing edit must not wait for or replace it with repository settings")
        }
        assertSame(persisted, restored.persisted)
        assertSame(draft, restored.draft)
        assertNotEquals(restored.persisted, restored.draft)
        assertEquals(dev.clickn.translate.data.RenderMode.BLOCKS, restored.persisted.renderMode)
        assertEquals(dev.clickn.translate.data.RenderMode.FLOATING_WINDOW, restored.draft.renderMode)
        assertEquals("owned-unsaved-key", restored.draft.apiKey)
    }

    @Test fun aScreenWithoutARetainedEditStillLoadsOneCompleteRepositorySnapshot() = runBlocking {
        val persisted = Settings(promptTemplate = "migrated prompt", floatingButtonAlpha = 0.4f)
        var reads = 0
        val restored = loadSettingsEditingSnapshot(null) { reads++; persisted }
        assertEquals(1, reads)
        assertSame(persisted, restored.persisted)
        assertSame(persisted, restored.draft)
    }

    @Test fun repeatedLocaleRestoreNeverPromotesUnsavedValuesToTheDirtyBaseline() = runBlocking {
        val persisted = Settings(renderMode = dev.clickn.translate.data.RenderMode.BLOCKS)
        var editing = SettingsEditingSnapshot(persisted, persisted.copy(
            renderMode = dev.clickn.translate.data.RenderMode.FLOATING_WINDOW))
        repeat(3) { index ->
            editing = loadSettingsEditingSnapshot(SettingsEditingSnapshot(editing.persisted,
                editing.draft.copy(model = "owned-draft-$index"))) { error("Unexpected reload") }
            assertSame(persisted, editing.persisted)
            assertNotEquals(editing.persisted, editing.draft)
            assertEquals("owned-draft-$index", editing.draft.model)
        }
    }

    @Test fun readsOnceAndOnlyMigratesKnownDefaults_tableDriven() = runBlocking {
        data class Case(val prompt: String, val expected: String, val writes: Int)
        listOf(
            Case("en-default", "en-default", 0),
            Case("zh-default", "en-default", 1),
            Case("custom prompt", "custom prompt", 0),
            Case("", "", 0),
        ).forEach { case ->
            var storage = Settings(promptTemplate = case.prompt, floatingButtonAlpha = 0.4f)
            var reads = 0
            var writes = 0
            val loaded = loadSettingsForScreen(
                read = { reads++; storage },
                update = { transform -> writes++; storage = transform(storage) },
                currentDefault = "en-default",
                knownDefaults = { listOf("en-default", "zh-default") },
            )
            assertEquals(case.prompt, 1, reads)
            assertEquals(case.prompt, case.writes, writes)
            assertEquals(case.expected, loaded.promptTemplate)
            assertEquals(0.4f, loaded.floatingButtonAlpha, 0f)
            assertEquals(storage, loaded)
        }
    }

    @Test fun concurrentPromptEditIsNotOverwritten_tableDriven() = runBlocking {
        for (concurrentPrompt in listOf("my edited prompt", "en-default", "zh-default")) {
            var storage = Settings(promptTemplate = "zh-default")
            val loaded = loadSettingsForScreen(
                read = { storage },
                update = { transform ->
                    storage = transform(storage.copy(promptTemplate = concurrentPrompt, floatingButtonAlpha = 0.6f))
                },
                currentDefault = "en-default",
                knownDefaults = { listOf("en-default", "zh-default") },
            )
            assertEquals(if (concurrentPrompt == "zh-default") "en-default" else concurrentPrompt, loaded.promptTemplate)
            assertEquals(0.6f, loaded.floatingButtonAlpha, 0f)
            assertEquals(storage, loaded)
        }
    }

    @Test fun noLocaleEnumerationWhenPromptAlreadyMatches() = runBlocking {
        loadSettingsForScreen(
            read = { Settings(promptTemplate = "en-default") },
            update = { fail("No migration required") },
            currentDefault = "en-default",
            knownDefaults = { error("Should not enumerate locales") },
        )
        Unit
    }

    @Test fun uiLoadsOneSnapshot() {
        val screen = File("src/main/java/dev/clickn/translate/ui/SettingsScreen.kt").readText()
        assertEquals(1, Regex("viewModel.loadForScreen\\(context\\)").findAll(screen).count())
        assertFalse(screen.contains("migrateDefaultPromptIfStale"))
        assertFalse(screen.contains("viewModel.load()"))
        assertTrue(screen.contains("val migratedPrompt = s.promptTemplate"))
    }
}
