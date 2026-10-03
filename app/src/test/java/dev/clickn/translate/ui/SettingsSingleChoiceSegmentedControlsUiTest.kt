// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SettingsSingleChoiceSegmentedControlsUiTest {
    @Test
    fun singleChoiceSettings_keepSelectionHandlersAcrossCardsAndWrappingChips() {
        val source = moduleFile(
            "src/main/java/dev/clickn/translate/ui/SettingsScreen.kt"
        ).readText()

        data class Case(
            val name: String,
            val startMarker: String,
            val endMarker: String,
            val requiredMarkers: List<String>,
            val forbiddenMarkers: List<String> = emptyList(),
        )

        val cases = listOf(
            Case(
                name = "display mode",
                startMarker = "val renderModeOptions =",
                endMarker = "if (renderMode == RenderMode.FLOATING_WINDOW)",
                requiredMarkers = listOf(
                    "RenderMode.BLOCKS",
                    "RenderMode.FLOATING_WINDOW",
                    "SettingChoiceCards(renderMode, renderModeOptions)",
                    "if (renderMode != mode)",
                ),
                forbiddenMarkers = listOf(
                    "enabled = mode != RenderMode.FLOATING_WINDOW || layoutControlsEnabled",
                ),
            ),
            Case(
                name = "translation block copy mode",
                startMarker = "val translationBlockCopyOptions =",
                endMarker = "val effectivePlacement =",
                requiredMarkers = listOf(
                    "TranslationBlockInteractionMode.COPY_BUTTON",
                    "TranslationBlockInteractionMode.OPEN_COPY_PANEL",
                    "selected = translationBlockInteractionMode == mode",
                    "if (translationBlockInteractionMode != mode)",
                ),
            ),
            Case(
                name = "merge strength",
                startMarker = "val mergeStrengthOptions =",
                endMarker = "stringResource(when (shownMergeStrength)",
                requiredMarkers = listOf(
                    "MergeStrength.CONSERVATIVE",
                    "MergeStrength.STANDARD",
                    "MergeStrength.AGGRESSIVE",
                    "MergeStrength.ALL",
                    "mergeStrengthOptionsFor(renderMode)",
                    "selected = shownMergeStrength == strength",
                    "if (mergeStrength != strength)",
                ),
            ),
            Case(
                name = "NiuTrans version",
                startMarker = "val niuTransModes =",
                endMarker = "SecretTextField(",
                requiredMarkers = listOf(
                    "NiuTransMode.FLASH",
                    "NiuTransMode.PRO",
                    "selected = niuTransMode == mode",
                    "if (niuTransMode != mode)",
                ),
            ),
        )

        cases.forEach { case ->
            val block = source.substring(
                source.indexOf(case.startMarker),
                source.indexOf(case.endMarker, source.indexOf(case.startMarker)),
            )
            val sharedMarkers = if (case.name == "display mode") listOf("SettingChoiceCards(") else listOf(
                "FlowRow(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp))",
                "SettingChoiceChip(", "icon = {}", "label = { Text(stringResource(labelRes)) }",
            )
            (sharedMarkers + case.requiredMarkers).forEach { marker ->
                assertTrue("${case.name}: missing $marker", block.contains(marker))
            }
            assertFalse("${case.name}: connected outlines are removed", block.contains("SegmentedButtonDefaults"))
            case.forbiddenMarkers.forEach { marker ->
                assertFalse("${case.name}: forbidden $marker", block.contains(marker))
            }
            assertFalse(
                "${case.name}: must no longer use loose chips",
                block.contains("EngineChip("),
            )
        }
    }

    private fun moduleFile(path: String): File = listOf(File(path), File("app", path))
        .firstOrNull(File::isFile)
        ?: error("Module file not found: $path")
}
