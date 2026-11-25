package dev.clickn.translate.ui

import dev.clickn.translate.data.AppCompanion
import dev.clickn.translate.data.CompanionPrefs
import org.junit.Assert.*
import org.junit.Test

class CompanionChoicesPolicyTest {
    @Test fun everyOwnedCharacterAndBothNonCharacterChoicesAreAvailableExactlyOnce() {
        val options = companionChoiceOptions(AppCompanion.CHESTER.id, hasCustomPicture = false)
        assertEquals(listOf("chester", "doc", "pancake", "bubu", "momo", "action", "logo"), options.map { it.first })
        assertEquals(options.size, options.map { it.first }.distinct().size)
        assertEquals(5, AppCompanion.entries.map { it.image }.distinct().size)
        assertTrue(options.all { it.second != 0 })
    }

    @Test fun missingCustomPictureNeverRemovesTheSavedCustomSelection() {
        val options = companionChoiceOptions(CompanionPrefs.CUSTOM, hasCustomPicture = false)
        assertTrue(options.any { it.first == CompanionPrefs.CUSTOM })
        assertEquals(8, options.size)
        assertFalse(companionChoiceOptions(CompanionPrefs.LOGO, false).any { it.first == CompanionPrefs.CUSTOM })
    }

    @Test fun anImportedPictureRemainsAnExplicitChoiceAfterSelectingAnOwnedCharacter() {
        val options = companionChoiceOptions(AppCompanion.DOC.id, hasCustomPicture = true)
        assertEquals(1, options.count { it.first == CompanionPrefs.CUSTOM })
        assertTrue(options.any { it.first == AppCompanion.DOC.id })
    }
}
