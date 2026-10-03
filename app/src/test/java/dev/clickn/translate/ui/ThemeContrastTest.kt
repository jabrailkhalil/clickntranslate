package dev.clickn.translate.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import dev.clickn.translate.ui.theme.*
import org.junit.Assert.*
import org.junit.Test

class ThemeContrastTest {
    private fun contrast(a: Color, b: Color): Float {
        val lighter = maxOf(a.luminance(), b.luminance())
        val darker = minOf(a.luminance(), b.luminance())
        return (lighter + .05f) / (darker + .05f)
    }

    @Test fun textRolesStayReadableInEveryThemeAndAccent() {
        themeChoices.forEach { (mode, _) ->
            ThemeAccent.entries.forEach { accent ->
                listOf(false, true).forEach { systemDark ->
                    val c = clickColorScheme(mode, accent, systemDark)
                    val pairs = listOf(
                        "page" to (c.onBackground to c.background),
                        "surface" to (c.onSurface to c.surface),
                        "secondary text" to (c.onSurfaceVariant to c.surfaceContainerHigh),
                        "button" to (c.onPrimary to c.primary),
                        "hero" to (c.onPrimaryContainer to c.primaryContainer),
                        "selected chip" to (c.onSecondaryContainer to c.secondaryContainer),
                        "error" to (c.onErrorContainer to c.errorContainer),
                        "error text" to (c.error to c.surface),
                    )
                    pairs.forEach { (role, pair) ->
                        val ratio = contrast(pair.first, pair.second)
                        assertTrue("mode=$mode accent=$accent $role contrast=$ratio", ratio >= 4.5f)
                        assertEquals("Opaque background: $role", 1f, pair.second.alpha, 0f)
                    }
                }
            }
        }
    }

    @Test fun paperPaletteIsIndependentOfSystemAppearance() {
        listOf(ThemeMode.PAPER_DAY, ThemeMode.PAPER_NIGHT, ThemeMode.PAPER_NORD).forEach {
            val lightSystem = clickColorScheme(it, systemDark = false)
            val darkSystem = clickColorScheme(it, systemDark = true)
            assertEquals(lightSystem.background, darkSystem.background)
            assertEquals(lightSystem.primary, darkSystem.primary)
            assertEquals(lightSystem.onSurfaceVariant, darkSystem.onSurfaceVariant)
        }
        val amoled = clickColorScheme(ThemeMode.AMOLED)
        assertEquals(Color.Black, amoled.background)
        assertEquals(Color.Black, amoled.surfaceContainerLowest)
    }
}
