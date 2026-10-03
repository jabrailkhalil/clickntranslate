package dev.clickn.translate.ui.theme

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/** Palettes and grid adapted from Komi Store's Manga personality; see theme_notices. */
internal fun komiPaperColors(mode: Int): ColorScheme? {
    val colors = when (mode) {
        ThemeMode.PAPER_DAY -> listOf(0xFFF1EADC, 0xFFFAF5EA, 0xFFE7DEC9, 0xFF1B150D, 0xFF625747, 0xFFB3261E, 0xFFFFFFFF)
        ThemeMode.PAPER_NIGHT -> listOf(0xFF0C0A07, 0xFF16120C, 0xFF211B12, 0xFFF0E9DA, 0xFFB9AD97, 0xFFFFB4AB, 0xFF690005)
        ThemeMode.PAPER_NORD -> listOf(0xFF2E3440, 0xFF3B4252, 0xFF434C5E, 0xFFECEFF4, 0xFFC1CBDC, 0xFFFFB4AB, 0xFF690005)
        else -> return null
    }.map { Color(it) }
    val (page, panel, well, ink, muted) = colors
    val base = if (mode == ThemeMode.PAPER_DAY) lightColorScheme() else darkColorScheme()
    val errorWell = if (mode == ThemeMode.PAPER_DAY) Color(0xFFFFDAD6) else Color(0xFF93000A)
    val errorInk = if (mode == ThemeMode.PAPER_DAY) Color(0xFF410002) else Color(0xFFFFDAD6)
    return base.copy(
        primary = ink, onPrimary = page, primaryContainer = well, onPrimaryContainer = ink,
        secondary = ink, onSecondary = page, secondaryContainer = well, onSecondaryContainer = ink,
        tertiary = ink, onTertiary = page, tertiaryContainer = well, onTertiaryContainer = ink,
        background = page, onBackground = ink, surface = panel, onSurface = ink,
        surfaceVariant = well, onSurfaceVariant = muted, surfaceTint = ink,
        surfaceBright = panel, surfaceDim = page, surfaceContainerLowest = page,
        surfaceContainerLow = panel, surfaceContainer = panel, surfaceContainerHigh = well,
        surfaceContainerHighest = well, inverseSurface = ink, inverseOnSurface = page, inversePrimary = panel,
        outline = muted, outlineVariant = if (mode == ThemeMode.PAPER_DAY) Color(0xFFB7AB96) else Color(0xFF665E52),
        error = colors[5], onError = colors[6], errorContainer = errorWell, onErrorContainer = errorInk,
    )
}

fun Modifier.komiPaperGrid(mode: Int, ink: Color): Modifier {
    if (mode !in ThemeMode.PAPER_DAY..ThemeMode.PAPER_NORD) return this
    return drawBehind {
        val step = 26.dp.toPx()
        val stroke = 1.dp.toPx()
        val color = ink.copy(alpha = if (mode == ThemeMode.PAPER_NIGHT) .06f else .05f)
        var x = 0f
        while (x < size.width) { drawLine(color, Offset(x, 0f), Offset(x, size.height), stroke); x += step }
        var y = 0f
        while (y < size.height) { drawLine(color, Offset(0f, y), Offset(size.width, y), stroke); y += step }
    }
}
