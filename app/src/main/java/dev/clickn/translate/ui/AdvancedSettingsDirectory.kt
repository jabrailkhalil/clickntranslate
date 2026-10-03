package dev.clickn.translate.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.outlined.VolumeUp
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.Settings

internal data class AdvancedCategory(val key: String, val title: Int, val summary: Int, val icon: ImageVector)
internal val advancedCategories = listOf(
    AdvancedCategory("general", R.string.refine_general, R.string.refine_general_body, Icons.Outlined.Palette),
    AdvancedCategory("translate", R.string.refine_translate, R.string.refine_translate_body, Icons.Outlined.Translate),
    AdvancedCategory("ocr", R.string.refine_ocr, R.string.refine_ocr_body, Icons.Outlined.DocumentScanner),
    AdvancedCategory("overlay", R.string.refine_overlay, R.string.refine_overlay_body, Icons.Outlined.Layers),
    AdvancedCategory("floating", R.string.refine_floating, R.string.refine_floating_body, Icons.Outlined.TouchApp),
    AdvancedCategory("capture_region", R.string.refine_region, R.string.refine_region_body, Icons.Outlined.CropFree),
    AdvancedCategory("word_select", R.string.refine_selection, R.string.refine_selection_body, Icons.Outlined.TextFields),
    AdvancedCategory("input_translation", R.string.refine_input, R.string.refine_input_body, Icons.Outlined.Keyboard),
    AdvancedCategory("tts", R.string.refine_speech, R.string.refine_speech_body, Icons.AutoMirrored.Outlined.VolumeUp),
    AdvancedCategory("trigger", R.string.refine_triggers, R.string.refine_triggers_body, Icons.Outlined.Bolt),
    AdvancedCategory("arc_menu", R.string.refine_menu, R.string.refine_menu_body, Icons.Outlined.GridView),
    AdvancedCategory("presets", R.string.refine_profiles, R.string.refine_profiles_body, Icons.Outlined.Bookmarks),
    AdvancedCategory("network", R.string.refine_network, R.string.refine_network_body, Icons.Outlined.Wifi),
    AdvancedCategory("developer", R.string.refine_diagnostics, R.string.refine_diagnostics_body, Icons.Outlined.BugReport),
)

@Composable
internal fun AdvancedSettingsDirectory(settings: Settings?, onSelect: (String) -> Unit) {
    LazyColumn(contentPadding = PaddingValues(24.dp, 8.dp, 24.dp, 100.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text(stringResource(R.string.refine_settings_intro), style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(bottom = 12.dp)) }
        items(advancedCategories, key = { it.key }) { category ->
            Surface(onClick = { onSelect(category.key) }, shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surfaceContainerLow) {
                Row(Modifier.fillMaxWidth().padding(20.dp), horizontalArrangement = Arrangement.spacedBy(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(category.icon, null, tint = MaterialTheme.colorScheme.primary)
                    Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(stringResource(category.title), fontWeight = FontWeight.SemiBold)
                        Text(stringResource(category.summary), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        val status = settings?.let { when (category.key) {
                            "translate" -> providerName(it.translatorEngine)
                            "ocr" -> stringResource(ocrEngineLabelRes(it.ocrEngine))
                            "tts" -> stringResource(if (it.ttsEnabled) R.string.refine_enabled else R.string.refine_disabled)
                            else -> null
                        } }
                        if (status != null) Text(status, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                    }
                    Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null)
                }
            }
        }
    }
}

/** A single Surface owns the background, outline, clipping and click target. */
@Composable
internal fun <T> SettingChoiceCards(value: T, options: List<Pair<T, Int>>, onSelect: (T) -> Unit) {
    Column(Modifier.fillMaxWidth().selectableGroup(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (option, label) ->
            val selected = value == option
            Surface(onClick = { onSelect(option) },
                modifier = Modifier.semantics { role = Role.RadioButton; this.selected = selected },
                shape = MaterialTheme.shapes.small,
                color = if (selected) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceContainer,
                border = BorderStroke(1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
                Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 16.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected, onClick = null)
                    Text(stringResource(label), Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                }
            }
        }
    }
}

@Composable
internal fun SettingChoiceChip(selected: Boolean, onClick: () -> Unit, icon: @Composable () -> Unit = {},
    label: @Composable () -> Unit, enabled: Boolean = true, modifier: Modifier = Modifier) {
    FilterChip(selected = selected, onClick = onClick, label = label, enabled = enabled,
        shape = MaterialTheme.shapes.small, modifier = modifier.heightIn(min = 48.dp))
}
