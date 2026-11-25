package dev.clickn.translate.ui

import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test

class SettingsEditingObservationTest {
    @Test fun lateEmissionsRefreshCleanFieldsAndRetainOnlyActualDraftEdits() = runBlocking {
        val baseline = Settings(translatorEngine = TranslatorEngine.GOOGLE_ML_KIT, apiKey = "synthetic-before")
        val values = MutableStateFlow(baseline)
        val editor = MutableStateFlow(SettingsEditingSnapshot(baseline, baseline.copy(captureLoopIntervalMs = 4_400)))
        val observer = launch(start = CoroutineStart.UNDISPATCHED) {
            observeSettingsEditing(editor.value, values, current = { editor.value }, apply = { editor.value = it })
        }
        try {
            val provider = baseline.copy(translatorEngine = TranslatorEngine.OPENAI,
                apiKey = "synthetic-after", model = "late model")
            values.value = provider
            val first = withTimeout(5_000) { editor.first { it.persisted == provider } }
            assertEquals(4_400L, first.draft.captureLoopIntervalMs)
            assertEquals(provider.apiKey, first.draft.apiKey)
            assertEquals(provider.model, first.draft.model)
            assertEquals(provider.captureLoopIntervalMs, first.persisted.captureLoopIntervalMs)

            editor.value = SettingsEditingSnapshot(first.persisted, first.draft.copy(promptTemplate = "My unsaved paragraph"))
            val next = provider.copy(pinnedLanguages = listOf("ar"), baseUrl = "https://latest.example.invalid")
            values.value = next
            val second = withTimeout(5_000) { editor.first { it.persisted == next } }
            assertEquals("My unsaved paragraph", second.draft.promptTemplate)
            assertEquals(4_400L, second.draft.captureLoopIntervalMs)
            assertEquals(next.baseUrl, second.draft.baseUrl)
            assertEquals(next.pinnedLanguages, second.draft.pinnedLanguages)
        } finally { observer.cancelAndJoin() }
    }

    @Test fun retainedLocaleDraftKeepsItsDirtyBaselineAndRebasesUneditedCredentials() {
        val persisted = Settings(apiKey = "synthetic-before", model = "before")
        val formBaseline = persisted.copy(ttsMimoVoiceSampleUri = "owned-normalized-form-default")
        val retained = SettingsEditingSnapshot(persisted, formBaseline.copy(captureLoopIntervalMs = 3_600), formBaseline)
        val latest = persisted.copy(apiKey = "synthetic-late", model = "late")

        val rebased = rebaseSettingsEditingSnapshot(retained, latest)

        assertSame(latest, rebased.persisted)
        assertEquals(latest.captureLoopIntervalMs, rebased.persisted.captureLoopIntervalMs)
        assertEquals(3_600L, rebased.draft.captureLoopIntervalMs)
        assertEquals(latest.apiKey, rebased.draft.apiKey)
        assertEquals(latest.model, rebased.draft.model)
        assertEquals(latest.ttsMimoVoiceSampleUri, rebased.draft.ttsMimoVoiceSampleUri)
        assertFalse(rebased.toString().contains("synthetic"))
    }
}
