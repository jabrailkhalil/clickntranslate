package dev.clickn.translate.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartMode

@Composable
internal fun MobileReadinessPanel(entries: List<MobileReadinessItem>, onOpen: () -> Unit) {
    val required = entries.filter { it.required }
    val completed = required.count { it.ready == true }
    val extra = entries.count { !it.required && it.ready != true }
    Surface(onClick = onOpen, modifier = Modifier.testTag("readiness-open"),
        shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Outlined.Checklist, null, tint = MaterialTheme.colorScheme.primary)
                Text(stringResource(R.string.readiness_title), Modifier.weight(1f).padding(horizontal = 12.dp),
                    style = MaterialTheme.typography.titleMedium)
                Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null)
            }
            LinearProgressIndicator(progress = { if (required.isEmpty()) 0f else completed.toFloat() / required.size },
                modifier = Modifier.fillMaxWidth().height(6.dp))
            Text(stringResource(R.string.readiness_core_progress, completed, required.size),
                style = MaterialTheme.typography.bodyMedium)
            Text(stringResource(if (extra > 0) R.string.readiness_more_available else R.string.readiness_recommendations_done),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
internal fun MobileReadinessSheet(entries: List<MobileReadinessItem>, captureMode: CaptureStartMode?,
    onItem: (MobileReadinessKey) -> Unit) {
    LazyColumn(Modifier.fillMaxWidth().testTag("readiness-checklist"), contentPadding = PaddingValues(24.dp, 0.dp, 24.dp, 32.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text(stringResource(R.string.readiness_title), style = MaterialTheme.typography.headlineSmall)
            Text(stringResource(R.string.readiness_body), Modifier.padding(top = 8.dp),
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        item { Text(stringResource(R.string.readiness_core), style = MaterialTheme.typography.titleMedium) }
        items(entries.filter { it.required }, key = { it.key }) { entry -> ReadinessSetting(entry, captureMode) { onItem(entry.key) } }
        item {
            HorizontalDivider(Modifier.padding(vertical = 4.dp))
            Text(stringResource(R.string.readiness_recommended), style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.readiness_recommended_body), Modifier.padding(top = 8.dp),
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(entries.filterNot { it.required }, key = { it.key }) { entry -> ReadinessSetting(entry, captureMode) { onItem(entry.key) } }
    }
}

@Composable
private fun ReadinessSetting(entry: MobileReadinessItem, captureMode: CaptureStartMode?, onClick: () -> Unit) {
    val title = when (entry.key) {
        MobileReadinessKey.LANGUAGES -> R.string.setup_translation
        MobileReadinessKey.SERVICE -> R.string.mobile_provider
        MobileReadinessKey.OCR -> R.string.setup_ocr
        MobileReadinessKey.TRANSLATION_MODELS -> R.string.setup_models
        MobileReadinessKey.OVERLAY -> R.string.setup_overlay
        MobileReadinessKey.CAPTURE -> R.string.setup_capture
        MobileReadinessKey.HERO -> R.string.readiness_hero
        MobileReadinessKey.NOTIFICATIONS -> R.string.setup_notifications
        MobileReadinessKey.BATTERY -> R.string.setup_battery
        MobileReadinessKey.ACCESSIBILITY -> R.string.setup_accessibility
    }
    val subtitle = when {
        entry.ready == null -> stringResource(R.string.refine_checking)
        entry.key == MobileReadinessKey.CAPTURE && captureMode != CaptureStartMode.SHIZUKU -> stringResource(R.string.readiness_system_capture)
        entry.key == MobileReadinessKey.CAPTURE && entry.ready -> stringResource(R.string.readiness_shizuku_enabled)
        entry.ready -> stringResource(R.string.refine_enabled)
        entry.required -> stringResource(R.string.refine_required)
        else -> stringResource(R.string.readiness_not_enabled)
    }
    Surface(onClick = onClick, modifier = Modifier.testTag("readiness-${entry.key.name.lowercase()}"),
        shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            when (entry.ready) {
                null -> CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 2.dp)
                true -> Icon(Icons.Outlined.CheckCircle, null, tint = MaterialTheme.colorScheme.primary)
                false -> Icon(if (entry.required) Icons.Outlined.RadioButtonUnchecked else Icons.Outlined.AddCircleOutline, null,
                    tint = if (entry.required) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(stringResource(title), style = MaterialTheme.typography.bodyLarge)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null)
        }
    }
}
