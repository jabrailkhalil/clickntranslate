// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.material3.Shapes
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp

// Click'n'Translate uses the lavender accent and neutral surfaces of clickn.dev.
private val ClickLight = lightColorScheme(
    primary = Color(0xFF6F3BBB), onPrimary = Color.White,
    primaryContainer = Color(0xFFECDDFF), onPrimaryContainer = Color(0xFF291542),
    secondary = Color(0xFF655574), onSecondary = Color.White,
    secondaryContainer = Color(0xFFEDE1F5), onSecondaryContainer = Color(0xFF2B2035),
    tertiary = Color(0xFF9B3D72), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFD8EA), onTertiaryContainer = Color(0xFF3E0929),
    background = Color(0xFFFCF9FF), onBackground = Color(0xFF211B28),
    surface = Color(0xFFFFFBFF), onSurface = Color(0xFF211B28),
    surfaceVariant = Color(0xFFEDE7F2), onSurfaceVariant = Color(0xFF5F5669),
    surfaceTint = Color(0xFF6F3BBB), surfaceBright = Color(0xFFFFFBFF),
    surfaceDim = Color(0xFFE4DDE8), surfaceContainer = Color(0xFFF3EEF7),
    surfaceContainerLowest = Color.White, surfaceContainerLow = Color(0xFFFCF9FF),
    surfaceContainerHigh = Color(0xFFEDE7F2), surfaceContainerHighest = Color(0xFFE6DFEC),
    inverseSurface = Color(0xFF2A2531), inverseOnSurface = Color(0xFFF3EEF7),
    inversePrimary = Color(0xFFB69AF7), outline = Color(0xFF82758D),
    outlineVariant = Color(0xFFD1C5DA), scrim = Color(0x66000000),
    error = Color(0xFFBA1A1A), onError = Color.White,
    errorContainer = Color(0xFFFFDAD6), onErrorContainer = Color(0xFF410002),
)
private val ClickDark = darkColorScheme(
    primary = Color(0xFFB69AF7), onPrimary = Color(0xFF291542),
    primaryContainer = Color(0xFF3C2856), onPrimaryContainer = Color(0xFFECDDFF),
    secondary = Color(0xFFD1BDD8), onSecondary = Color(0xFF35283F),
    secondaryContainer = Color(0xFF4D3F57), onSecondaryContainer = Color(0xFFEDE1F5),
    tertiary = Color(0xFFF4AED4), onTertiary = Color(0xFF5E1F46),
    tertiaryContainer = Color(0xFF7C315C), onTertiaryContainer = Color(0xFFFFD8EA),
    background = Color(0xFF0B0B0D), onBackground = Color(0xFFF3F0F7),
    surface = Color(0xFF17151C), onSurface = Color(0xFFF3F0F7),
    surfaceVariant = Color(0xFF272131), onSurfaceVariant = Color(0xFFC3BACD),
    surfaceTint = Color(0xFFB69AF7), surfaceBright = Color(0xFF38313F),
    surfaceDim = Color(0xFF0B0B0D), surfaceContainer = Color(0xFF1C1822),
    surfaceContainerLowest = Color(0xFF08070A), surfaceContainerLow = Color(0xFF17151C),
    surfaceContainerHigh = Color(0xFF272131), surfaceContainerHighest = Color(0xFF322A3C),
    inverseSurface = Color(0xFFEAE3F0), inverseOnSurface = Color(0xFF302938),
    inversePrimary = Color(0xFF6F3BBB), outline = Color(0xFF9B8EA8),
    outlineVariant = Color(0xFF4E435A), scrim = Color(0x99000000),
    error = Color(0xFFFFB4AB), onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A), onErrorContainer = Color(0xFFFFDAD6),
)

object ThemeMode {
    const val FOLLOW_SYSTEM = 0
    const val LIGHT = 1
    const val DARK = 2
    const val AMOLED = 3
    const val PAPER_DAY = 4
    const val PAPER_NIGHT = 5
    const val PAPER_NORD = 6
}

@Composable
fun ClickTranslateTheme(
    themeMode: Int = ThemeMode.FOLLOW_SYSTEM,
    accent: ThemeAccent = ThemeAccent.LAVENDER,
    content: @Composable () -> Unit,
) {
    val darkTheme = when (themeMode) {
        ThemeMode.LIGHT -> false
        ThemeMode.DARK, ThemeMode.AMOLED -> true
        else -> isSystemInDarkTheme()
    }
    val base = if (darkTheme) ClickDark else ClickLight
    val primary = Color(if (darkTheme) accent.darkColor else accent.lightColor)
    val palette = base.copy(
        primary = primary,
        onPrimary = if (darkTheme) Color(0xFF101116) else Color.White,
        primaryContainer = lerp(primary, if (darkTheme) Color(0xFF111217) else Color.White, if (darkTheme) 0.73f else 0.89f),
        onPrimaryContainer = if (darkTheme) Color(0xFFF2F0F7) else Color(0xFF17131D),
        surfaceTint = primary,
        background = if (themeMode == ThemeMode.AMOLED) Color.Black else base.background,
        surface = if (themeMode == ThemeMode.AMOLED) Color(0xFF0D0D10) else base.surface,
        surfaceContainer = if (themeMode == ThemeMode.AMOLED) Color(0xFF121216) else base.surfaceContainer,
    )
    val paper = komiPaperColors(themeMode)
    val colors = paper ?: palette
    MaterialTheme(
        colorScheme = colors,
        shapes = if (paper != null) Shapes(small = RoundedCornerShape(0.dp), medium = RoundedCornerShape(0.dp), large = RoundedCornerShape(0.dp))
            else Shapes(small = RoundedCornerShape(12.dp), medium = RoundedCornerShape(24.dp), large = RoundedCornerShape(32.dp)),
        content = {
            androidx.compose.runtime.CompositionLocalProvider(androidx.compose.material3.LocalContentColor provides colors.onBackground) { content() }
        },
    )
}
