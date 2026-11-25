package dev.clickn.translate.ui

import dev.clickn.translate.data.AutoOcrRoute
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.Settings
import org.junit.Assert.*
import org.junit.Test

class TesseractModelAdmissionPolicyTest {
    @Test fun noKeyIsNeededButUnverifiedArabicModelsCannotBeSelected() {
        val route = AutoOcrRoute(OcrEngineKind.TESSERACT_ARABIC)
        for ((available, expected) in listOf(null to AutoOcrOptionState.CHECKING,
            emptySet<AutoOcrRoute>() to AutoOcrOptionState.DOWNLOAD,
            setOf(route) to AutoOcrOptionState.READY)) {
            val state = autoOcrOptionState(Settings(), "ar", route, available, emptySet())
            assertEquals(expected, state)
            assertEquals(expected == AutoOcrOptionState.READY, autoOcrCanSelect(Settings(), "ar", route, state))
        }
    }

    @Test fun deletingOrCancellingMissingModelsDoesNotCreateReadinessOrCrossLanguageSupport() {
        val route = AutoOcrRoute(OcrEngineKind.TESSERACT_ARABIC)
        val installed = autoOcrOptionState(Settings(), "en", route, setOf(route), emptySet())
        assertTrue(autoOcrCanSelect(Settings(), "en", route, installed))
        val missingAfterDeleteOrFailedDownload = autoOcrOptionState(Settings(), "en", route, emptySet(), emptySet())
        assertEquals(AutoOcrOptionState.DOWNLOAD, missingAfterDeleteOrFailedDownload)
        assertFalse(autoOcrCanSelect(Settings(), "en", route, missingAfterDeleteOrFailedDownload))
        val unsupported = autoOcrOptionState(Settings(), "ru", route, setOf(route), emptySet())
        assertEquals(AutoOcrOptionState.UNSUPPORTED, unsupported)
        assertFalse(autoOcrCanSelect(Settings(), "ru", route, unsupported))
    }
}
