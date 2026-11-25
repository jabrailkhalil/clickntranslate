package dev.clickn.translate.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.OverlayTheme

/** Each choice is measured against the group width before a new row is needed. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun SettingsOptionGroup(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    FlowRow(
        modifier = modifier.fillMaxWidth().selectableGroup(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) { content() }
}

@Composable
internal fun OverlayThemeChoices(current: OverlayTheme, onSelect: (OverlayTheme) -> Unit) {
    SettingsOptionGroup {
        EngineChip(current, OverlayTheme.CLASSIC_DARK, stringResource(R.string.settings_theme_classic_dark), onSelect = onSelect)
        EngineChip(current, OverlayTheme.AMBER_GOLD, stringResource(R.string.settings_theme_amber_gold), onSelect = onSelect)
        EngineChip(current, OverlayTheme.PAPER_LIGHT, stringResource(R.string.settings_theme_paper_light), onSelect = onSelect)
        EngineChip(current, OverlayTheme.FROST_GLASS, stringResource(R.string.settings_theme_frost_glass), onSelect = onSelect)
        EngineChip(current, OverlayTheme.CUSTOM, stringResource(R.string.settings_theme_custom), onSelect = onSelect)
    }
}
