// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class MangaEraseCoverageWiringTest {

    @Test
    fun delayedRepair_tableDriven_preservesSemanticGeometryAndRejectsPartialCoverage() {
        data class Case(val name: String, val path: String, val marker: String)

        listOf(
            Case(
                name = "blocks without child boxes still use their visible geometry",
                path = "src/main/java/dev/clickn/translate/ocr/MangaDelayedMaskDebugSession.kt",
                marker = "block.sourceBoxesOrBoundingBox()",
            ),
            Case(
                name = "outer text geometry remains separate from detector members",
                path = "src/main/java/dev/clickn/translate/ocr/MangaDelayedMaskDebugSession.kt",
                marker = "semanticBounds = IntRect(",
            ),
            Case(
                name = "text patches require coverage of actual erase targets",
                path = "src/main/java/dev/clickn/translate/ocr/LocalTextBackgroundRepairer.kt",
                marker = "requiredCoveragePixels = requiredErasePixels",
            ),
            Case(
                name = "model bubble patches also require completion coverage",
                path = "src/main/java/dev/clickn/translate/ocr/LocalBubbleBackgroundRepairer.kt",
                marker = "repairedCompletionPixels.toFloat()",
            ),
        ).forEach { case ->
            assertTrue(case.name, sourceFile(case.path).readText().contains(case.marker))
        }
    }

    private fun sourceFile(path: String): File =
        listOf(File(path), File("app", path)).firstOrNull(File::isFile)
            ?: error("Source file not found: $path")
}
