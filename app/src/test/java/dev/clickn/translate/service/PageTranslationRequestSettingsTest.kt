package dev.clickn.translate.service

import dev.clickn.translate.data.RuntimeTranslationVisualContext
import dev.clickn.translate.data.RuntimeVisualTextItem
import dev.clickn.translate.data.Settings
import dev.clickn.translate.translate.PageTranslationUnit
import org.junit.Assert.*
import org.junit.Test

class PageTranslationRequestSettingsTest {
    @Test fun retryOfTheThirdBlockKeepsItsOwnCoordinatesAndUsesTheFirstRequestId() {
        val original = Settings(runtimeTranslationVisualContext = fixture())
        val request = settingsForPendingPageUnits(original, listOf(PageTranslationUnit(2, "third source")))
        val visual = requireNotNull(request.runtimeTranslationVisualContext)
        assertEquals(listOf(RuntimeVisualTextItem(1, "third source", 20, 100, 90, 140)), visual.items)
        assertEquals("owned-image", visual.base64Data)
        assertEquals(fixture(), original.runtimeTranslationVisualContext)
    }

    @Test fun nonAdjacentPendingUnitsAreMappedInSubmittedOrderWithoutResendingAcceptedUnits() {
        val request = settingsForPendingPageUnits(Settings(runtimeTranslationVisualContext = fixture()),
            listOf(PageTranslationUnit(2, "third source"), PageTranslationUnit(0, "first source")))
        val items = requireNotNull(request.runtimeTranslationVisualContext).items
        assertEquals(listOf(1, 2), items.map { it.id })
        assertEquals(listOf("third source", "first source"), items.map { it.source })
        assertEquals(listOf(100, 10), items.map { it.top })
    }

    @Test fun mergedVisualOutputKeepsAllItsBoxesButMissingGeometryUsesTextFallback() {
        val merged = Settings(runtimeTranslationVisualContext = fixture().copy(combineIntoSingleOutput = true))
        assertSame(merged, settingsForPendingPageUnits(merged,
            listOf(PageTranslationUnit(0, "all sources", blockIndexes = listOf(0, 1, 2)))))
        val missing = settingsForPendingPageUnits(Settings(runtimeTranslationVisualContext = fixture()),
            listOf(PageTranslationUnit(9, "unlocated source")))
        assertNull(missing.runtimeTranslationVisualContext)
        val plain = Settings()
        assertSame(plain, settingsForPendingPageUnits(plain, listOf(PageTranslationUnit(0, "source"))))
    }

    private fun fixture() = RuntimeTranslationVisualContext("image/jpeg", "owned-image", 100, 200, 10,
        "owned-hash", listOf(
            RuntimeVisualTextItem(1, "first source", 20, 10, 90, 40),
            RuntimeVisualTextItem(2, "second source", 20, 50, 90, 80),
            RuntimeVisualTextItem(3, "third source", 20, 100, 90, 140),
        ), combineIntoSingleOutput = false)
}
