package dev.clickn.translate.glossary

import dev.clickn.translate.data.Settings
import kotlinx.serialization.json.Json
import org.junit.Assert.*
import org.junit.Test

class SourcePresetPolicyTest {
    private val sounds = setOf("ドン", "ガチャ")
    private val seed = GlossaryTermEntity(id = 1, sourceLang = "ja", targetLang = "*", sourceTerm = "ドン",
        targetTerm = "ドン", category = GlossaryTermCategory.PRESERVE_SOURCE, createdAtMs = 1, updatedAtMs = 1)
    @Test fun oldPresetIsHiddenOnlyWhileUntouched() {
        assertTrue(SourcePresetPolicy.isUntouchedLegacySeed(seed, sounds))
        listOf(seed.copy(updatedAtMs = 2), seed.copy(enabled = false), seed.copy(scopePackage = "org.telegram.messenger"),
            seed.copy(targetTerm = "Boom"), seed.copy(sourceTerm = "Custom"), seed.copy(caseSensitive = true),
            seed.copy(category = GlossaryTermCategory.TERM)).forEach {
            assertFalse(SourcePresetPolicy.isUntouchedLegacySeed(it, sounds))
        }
    }
    @Test fun builtInWordsAreOptInAndDoNotAppearWhenOff() {
        assertFalse(Settings().mangaSoundEffectsEnabled)
        assertFalse(Json.decodeFromString<Settings>("{}").mangaSoundEffectsEnabled)
        assertTrue(SourcePresetPolicy.activeTerms(emptyList(), sounds, false).isEmpty())
        assertEquals(sounds, SourcePresetPolicy.activeTerms(emptyList(), sounds, true).map { it.sourceTerm }.toSet())
    }
    @Test fun editedAndDisabledUserEntriesOverrideThePack() {
        val disabled = seed.copy(enabled = false, updatedAtMs = 2)
        val active = SourcePresetPolicy.activeTerms(listOf(disabled), sounds, true)
        assertEquals(listOf("ガチャ"), active.map { it.sourceTerm })
        val custom = seed.copy(targetTerm = "Own spelling", updatedAtMs = 2)
        assertEquals(custom, SourcePresetPolicy.activeTerms(listOf(custom), sounds, true).first())
        assertEquals(1, SourcePresetPolicy.activeTerms(listOf(custom), sounds, true).count { it.sourceTerm == "ドン" })
    }
    @Test fun unrelatedGlossaryTermsNeverPreserveScreenText() {
        val ordinary = seed.copy(category = GlossaryTermCategory.TERM)
        assertTrue(SourcePresetPolicy.activeTerms(listOf(ordinary), sounds, false).isEmpty())
    }
}
