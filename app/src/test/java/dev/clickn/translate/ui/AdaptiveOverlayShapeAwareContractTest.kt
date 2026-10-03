// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.data.OverlayStyleMode
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.data.adaptiveOverlayActive
import dev.clickn.translate.ocr.MangaShapeAwareFramePolicy
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AdaptiveOverlayShapeAwareContractTest {
    @Test
    fun adaptiveOverlay_isTheOnlyShapeAwareSwitch_tableDriven() {
        data class Case(
            val name: String,
            val style: OverlayStyleMode,
            val renderMode: RenderMode,
            val expected: Boolean,
        )

        listOf(
            Case("adaptive blocks", OverlayStyleMode.ADAPTIVE, RenderMode.BLOCKS, true),
            Case("fixed blocks", OverlayStyleMode.FIXED, RenderMode.BLOCKS, false),
            Case(
                "floating window",
                OverlayStyleMode.ADAPTIVE,
                RenderMode.FLOATING_WINDOW,
                false,
            ),
        ).forEach { case ->
            val enabled = adaptiveOverlayActive(case.style, case.renderMode)
            assertEquals(case.name, case.expected, enabled)
            val decision = MangaShapeAwareFramePolicy.decide(
                shapeAwareRenderingEnabled = enabled,
                developerOptionsEnabled = false,
                screenshotSavingEnabled = false,
                bubbleDetectorAvailable = true,
                localSegmentationModelAvailable = false,
            )
            assertEquals(case.name, case.expected, decision.analyzeFrame)
            assertEquals(case.name, case.expected, decision.createDelayedSession)
        }
    }

    @Test
    fun independentShapeAwareSettingAndUi_areRemoved() {
        val allSources = listOf(
            "src/main/java/dev/clickn/translate/data/Settings.kt",
            "src/main/java/dev/clickn/translate/data/SettingsRepository.kt",
            "src/main/java/dev/clickn/translate/ui/SettingsScreen.kt",
            "src/main/java/dev/clickn/translate/ui/SettingsViewModel.kt",
        ).joinToString("\n") { moduleFile(it).readText() }

        listOf(
            "mangaShapeAwareEnabled",
            "MangaShapeAwareSection",
            "saveMangaShapeAwareEnabled",
        ).forEach { marker ->
            assertFalse("independent switch remains: $marker", allSources.contains(marker))
        }

        listOf(
            "src/main/java/dev/clickn/translate/ocr/MangaOcrEngine.kt",
            "src/main/java/dev/clickn/translate/ocr/PaddleOcrEngine.kt",
        ).forEach { path ->
            val source = moduleFile(path).readText()
            assertTrue("$path must use adaptive overlay", source.contains("adaptiveOverlayActive("))
        }
    }

    private fun moduleFile(path: String): File = listOf(File(path), File("app", path))
        .firstOrNull(File::isFile)
        ?: error("Module file not found: $path")
}
