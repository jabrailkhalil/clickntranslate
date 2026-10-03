// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.R
import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class OrientationModelVisibilityPolicyTest {

    @Test
    fun hiddenPackage_tableDriven_neverBecomesPresetRequirement() {
        data class Case(
            val name: String,
            val autoDetect: Boolean,
            val modelReady: Boolean,
        )

        listOf(
            Case("automatic detection off and model missing", autoDetect = false, modelReady = false),
            Case("automatic detection on and model missing", autoDetect = true, modelReady = false),
            Case("automatic detection on and model ready", autoDetect = true, modelReady = true),
            Case("automatic detection off and model ready", autoDetect = false, modelReady = true),
        ).forEach { case ->
            assertFalse(
                case.name,
                OrientationModelVisibilityPolicy.shouldReportMissingForPreset(
                    textOrientationAutoDetect = case.autoDetect,
                    modelReady = case.modelReady,
                ),
            )
        }
    }

    @Test
    fun hiddenPackage_smoke_hidesSearchButRetainsImplementation() {
        assertFalse(OrientationModelVisibilityPolicy.userManagementVisible)
        assertFalse(
            "hidden model must not remain discoverable through settings search",
            R.string.settings_search_item_orientation_model in settingsSearchItemLabelResIds(),
        )

        val settingsSource = File("src/main/java/dev/clickn/translate/ui/SettingsScreen.kt").readText()
        val viewModelSource = File("src/main/java/dev/clickn/translate/ui/SettingsViewModel.kt").readText()
        assertTrue(settingsSource.contains("private fun OrientationModelSection("))
        assertTrue(settingsSource.contains("OrientationModelVisibilityPolicy.userManagementVisible"))
        assertTrue(viewModelSource.contains("fun downloadOrientationModel("))
        assertTrue(viewModelSource.contains("fun deleteOrientationModel("))
    }
}
