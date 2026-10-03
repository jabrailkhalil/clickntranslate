// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class InputTranslationSettingsUiTest {

    @Test
    fun inputTranslationCard_usesExistingSegmentedControlAndPersistsSelection() {
        val source = moduleFile("src/main/java/dev/clickn/translate/ui/SettingsScreen.kt").readText()
        val start = source.indexOf("item(key = SectionKeys.INPUT_TRANSLATION)")
        val trigger = source.indexOf("item(key = SectionKeys.TRIGGER)")
        val end = source.indexOf("item(key = SectionKeys.ARC_MENU)", start)
        val card = source.substring(start, end)

        assertTrue("input translation card must be before loop settings", start in 0 until trigger)

        listOf(
            "SectionCard(title = stringResource(R.string.settings_section_input_translation))",
            "FlowRow(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp))",
            "InputTranslationDoubleAction.FULL_SCREEN",
            "InputTranslationDoubleAction.WORD_SELECT",
            "viewModel.saveInputTranslationDoubleAction(action)",
            "AndroidSettings.ACTION_ACCESSIBILITY_SETTINGS",
            "enabled = !accessibilityServiceEnabled",
            "R.string.settings_btn_a11y_enabled",
        ).forEach { marker ->
            assertTrue("missing $marker", card.contains(marker))
        }
    }

    private fun moduleFile(path: String): File = listOf(File(path), File("app", path))
        .firstOrNull(File::isFile)
        ?: error("Module file not found: $path")
}
