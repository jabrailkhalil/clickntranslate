package dev.clickn.translate.service

import dev.clickn.translate.data.Settings
import dev.clickn.translate.translate.PageTranslationUnit

/** Structured providers number each submitted list from one, including a partial-page retry. */
internal fun settingsForPendingPageUnits(settings: Settings, units: List<PageTranslationUnit>): Settings {
    val visual = settings.runtimeTranslationVisualContext ?: return settings
    if (visual.combineIntoSingleOutput && units.size == 1) return settings
    if (visual.combineIntoSingleOutput) return settings.copy(runtimeTranslationVisualContext = null)
    val items = units.mapIndexed { requestIndex, unit ->
        // Geometry belongs to the original OCR block, not the compacted pending-list index.
        val item = visual.items.singleOrNull { it.id == unit.blockIndex + 1 }
        if (item == null || unit.blockIndexes != listOf(unit.blockIndex)) {
            // An item with no proven geometry cannot be grounded in a different item's box.
            // The existing provider text fallback still translates the requested OCR source.
            return settings.copy(runtimeTranslationVisualContext = null)
        }
        item.copy(id = requestIndex + 1, source = unit.sourceText)
    }
    return settings.copy(runtimeTranslationVisualContext = visual.copy(items = items))
}
