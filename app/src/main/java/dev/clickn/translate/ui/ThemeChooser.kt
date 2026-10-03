package dev.clickn.translate.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.ui.theme.*

internal val themeChoices = listOf(
    ThemeMode.FOLLOW_SYSTEM to R.string.mobile_system,
    ThemeMode.LIGHT to R.string.mobile_light,
    ThemeMode.DARK to R.string.mobile_dark,
    ThemeMode.AMOLED to R.string.mobile_amoled,
    ThemeMode.PAPER_DAY to R.string.refine_paper_day,
    ThemeMode.PAPER_NIGHT to R.string.refine_paper_night,
    ThemeMode.PAPER_NORD to R.string.refine_paper_nord,
)

@Composable
internal fun ThemeChoices() {
    Column(Modifier.fillMaxWidth().selectableGroup(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        themeChoices.chunked(2).forEach { choices -> ThemeChoiceRow(choices) }
    }
}

@Composable
internal fun ThemeChoiceRow(choices: List<Pair<Int, Int>>) {
    val theme = LocalThemeMode.current
    val accent = LocalThemeAccent.current.accent
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        choices.forEach { (mode, label) ->
            val selected = theme.mode == mode
            Surface(
                modifier = Modifier.weight(1f).testTag("theme-$mode")
                    .selectable(selected, role = Role.RadioButton, onClick = { theme.setMode(mode) }),
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceContainerLow,
                border = BorderStroke(if (selected) 2.dp else 1.dp,
                    if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    ThemeMiniature(mode, accent, Modifier.fillMaxWidth().height(88.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(stringResource(label), Modifier.weight(1f), style = MaterialTheme.typography.labelLarge,
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal)
                        if (selected) Icon(Icons.Outlined.CheckCircle, null, Modifier.size(20.dp),
                            tint = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
        if (choices.size == 1) Spacer(Modifier.weight(1f))
    }
}

/** Uses the production palettes, so the preview always matches the selected theme. */
@Composable
private fun ThemeMiniature(mode: Int, accent: ThemeAccent, modifier: Modifier) {
    val colors = clickColorScheme(if (mode == ThemeMode.FOLLOW_SYSTEM) ThemeMode.LIGHT else mode, accent)
    val dark = clickColorScheme(ThemeMode.DARK, accent)
    Canvas(modifier) {
        fun panel(palette: ColorScheme, left: Float, width: Float) {
            val gap = 8.dp.toPx()
            drawRoundRect(palette.background, Offset(left, 0f), Size(width, size.height), CornerRadius(gap))
            drawRoundRect(palette.surfaceContainerHigh, Offset(left + gap, gap),
                Size(width - gap * 2, size.height * .53f), CornerRadius(gap * .7f))
            drawRoundRect(palette.onSurface, Offset(left + gap * 2, gap * 2),
                Size((width - gap * 4) * .7f, 4.dp.toPx()), CornerRadius(2.dp.toPx()))
            drawRoundRect(palette.onSurfaceVariant, Offset(left + gap * 2, gap * 3),
                Size((width - gap * 4) * .9f, 3.dp.toPx()), CornerRadius(2.dp.toPx()))
            drawRoundRect(palette.primary, Offset(left + gap, size.height * .7f),
                Size(width - gap * 2, size.height * .19f), CornerRadius(gap))
            drawRoundRect(palette.onPrimary, Offset(left + width * .36f, size.height * .775f),
                Size(width * .28f, 3.dp.toPx()), CornerRadius(2.dp.toPx()))
        }
        if (mode == ThemeMode.FOLLOW_SYSTEM) {
            panel(colors, 0f, size.width / 2f)
            panel(dark, size.width / 2f, size.width / 2f)
        } else panel(colors, 0f, size.width)
    }
}
