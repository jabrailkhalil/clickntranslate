package dev.clickn.translate.data

import org.junit.Assert.*
import org.junit.Test

class SettingsEditorChangesTest {
    @Test fun loopOnlyEditDoesNotRestoreOldProviderConnectionOrCredentials() {
        val baseline = Settings(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT,
            baseUrl = "https://before.example.invalid", apiKey = "synthetic-before", model = "before")
        val draft = baseline.copy(captureLoopIntervalMs = 4_400)
        val latest = baseline.copy(translatorEngine = TranslatorEngine.OPENAI,
            baseUrl = "https://after.example.invalid", apiKey = "synthetic-after", model = "after")
        val edits = SettingsEditorChanges.between(baseline, draft)
        val merged = edits.applyTo(latest)

        assertEquals(setOf("captureLoopIntervalMs"), edits.fieldNames)
        assertEquals(4_400L, merged.captureLoopIntervalMs)
        assertEquals(latest.translatorEngine, merged.translatorEngine)
        assertEquals(latest.baseUrl, merged.baseUrl)
        assertEquals(latest.apiKey, merged.apiKey)
        assertEquals(latest.model, merged.model)
        assertFalse(edits.toString().contains("synthetic"))
    }

    @Test fun normalizationIsAppliedOnlyToExplicitlyEditedFields() {
        val baseline = Settings(apiKey = " synthetic-before ", model = " before ")
        val draft = baseline.copy(captureLoopIntervalMs = 3_000)
        val normalized = draft.copy(apiKey = draft.apiKey.trim(), model = draft.model.trim())
        val latest = baseline.copy(apiKey = "synthetic-new", model = "new")

        val merged = SettingsEditorChanges.between(baseline, draft).applyTo(latest, normalized)

        assertEquals("synthetic-new", merged.apiKey)
        assertEquals("new", merged.model)
        assertEquals(3_000L, merged.captureLoopIntervalMs)
    }

    @Test fun explicitSameFieldEditsWinWhileLatePresetAndExportMetadataStayCurrent() {
        val baseline = Settings(model = "before")
        val draft = baseline.copy(model = "my edited model", overlayAlpha = 0.61f,
            promptTemplate = "Owned paragraph العربية")
        val preset = TranslationPresetCatalog.fromSettings("custom_late", "Late profile", "L", baseline)
        val latest = baseline.copy(model = "other writer model", pinnedLanguages = listOf("ar"),
            translationPresets = listOf(preset), activeTranslationPresetId = preset.id,
            captureRegionSavedScreenW = 1080, captureRegionSavedScreenH = 2400)

        val merged = SettingsEditorChanges.between(baseline, draft).applyTo(latest)

        assertEquals(draft.model, merged.model)
        assertEquals(draft.overlayAlpha, merged.overlayAlpha)
        assertEquals(draft.promptTemplate, merged.promptTemplate)
        assertEquals(latest.translationPresets, merged.translationPresets)
        assertEquals(latest.activeTranslationPresetId, merged.activeTranslationPresetId)
        assertEquals(latest.pinnedLanguages, merged.pinnedLanguages)
        assertEquals(1080, merged.captureRegionSavedScreenW)
        assertEquals(2400, merged.captureRegionSavedScreenH)
    }

    @Test fun transientRequestStateIsAlwaysTakenFromLatestRatherThanSerializerDefaultsOrDraft() {
        val baseline = Settings(runtimeTranslationContext = "before", runtimeTranslationScopePackage = "before.package")
        val draft = baseline.copy(overlayAlpha = 0.5f, runtimeTranslationContext = "editor must not write this",
            runtimeTranslationScopePackage = "editor.package", runtimeTranslationScopeLabel = "editor label")
        val latest = baseline.copy(runtimeTranslationContext = "current request", runtimeTranslationScopePackage = "",
            runtimeTranslationScopeLabel = "current scope")

        val merged = SettingsEditorChanges.between(baseline, draft).applyTo(latest)

        assertEquals(0.5f, merged.overlayAlpha)
        assertEquals("current request", merged.runtimeTranslationContext)
        assertEquals("", merged.runtimeTranslationScopePackage)
        assertEquals("current scope", merged.runtimeTranslationScopeLabel)
        assertSame(latest.runtimeTranslationPromptContext, merged.runtimeTranslationPromptContext)
        assertSame(latest.runtimeTranslationVisualContext, merged.runtimeTranslationVisualContext)
        assertTrue(SettingsEditorChanges.between(baseline, baseline.copy(runtimeTranslationContext = "ignored")).isEmpty)
    }
}
