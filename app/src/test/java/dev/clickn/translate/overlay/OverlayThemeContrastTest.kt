package dev.clickn.translate.overlay

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.graphics.luminance
import dev.clickn.translate.data.*
import org.junit.Assert.*
import org.junit.Test

class OverlayThemeContrastTest {
    @Test fun builtInTextAndActionsStayReadableOverLightAndDarkApplications() {
        OverlayTheme.entries.filter { it != OverlayTheme.CUSTOM }.forEach { theme ->
            val palette = builtInOverlayPalette(theme)!!
            assertEquals(palette.accent, translationActionAccentColor(theme, 0, 0))
            listOf(1f, Settings().overlayAlpha).forEach { windowAlpha ->
                listOf(Color.White, Color.Black).forEach { underneath ->
                    val background = Color(palette.background)
                    val bg = background.copy(alpha = background.alpha * windowAlpha).compositeOver(underneath)
                    listOf(palette.foreground, palette.muted, palette.accent).forEach { argb ->
                        val fg = Color(argb).copy(alpha = windowAlpha).compositeOver(underneath)
                        val a = fg.luminance(); val b = bg.luminance()
                        val ratio = (maxOf(a, b) + .05f) / (minOf(a, b) + .05f)
                        assertTrue("$theme alpha=$windowAlpha contrast=$ratio", ratio >= 4.5f)
                    }
                }
            }
        }
        assertNull(builtInOverlayPalette(OverlayTheme.CUSTOM))
    }
}
