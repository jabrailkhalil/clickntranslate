// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.data.RenderMode
import org.junit.Assert.assertEquals
import org.junit.Test

class OverlayPreviewModeTest {

    @Test
    fun floatingWindowPreviewPolicy_tableDriven_matchesRenderMode() {
        data class Case(val name: String, val mode: RenderMode, val expected: Boolean)

        listOf(
            Case("translation blocks keep the block preview", RenderMode.BLOCKS, false),
            Case("floating window uses the window preview", RenderMode.FLOATING_WINDOW, true),
        ).forEach { case ->
            assertEquals(case.name, case.expected, overlayPreviewUsesFloatingWindow(case.mode))
        }
    }
}
