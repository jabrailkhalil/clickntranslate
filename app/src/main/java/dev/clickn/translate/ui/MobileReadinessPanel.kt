package dev.clickn.translate.ui

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.Settings

@Composable
internal fun MobileReadinessPanel(settings: Settings, models: MobileModelState,
    overlay: Boolean, accessibility: Boolean, notifications: Boolean, battery: Boolean,
    onOverlay: () -> Unit, onService: () -> Unit, onOcr: () -> Unit, onModels: () -> Unit,
    onAccessibility: () -> Unit, onNotifications: () -> Unit, onBattery: () -> Unit, onCapture: () -> Unit = onOverlay) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    val serviceReady = !translationNeedsConfiguration(settings)
    val needsModels = settings.translatorEngine in offlineTranslationEngines && models.translationReady != true
    val ready = overlay && serviceReady && !models.checking && models.ocrReady == true && !needsModels
    Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceContainerLow) {
        Column(Modifier.fillMaxWidth().padding(20.dp)) {
            Text(stringResource(if (ready) R.string.polish_ready else R.string.refine_readiness), style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(12.dp))
            if (!overlay || expanded) ReadinessRow(R.string.setup_overlay, overlay, true, Icons.Outlined.Layers, onOverlay)
            if (!serviceReady || expanded) ReadinessRow(R.string.mobile_services, serviceReady, true, Icons.Outlined.Translate, onService, providerName(settings.translatorEngine))
            if (models.ocrReady != true || models.checking || expanded) {
                ReadinessRow(R.string.setup_ocr, if (models.checking) null else models.ocrReady, true, Icons.Outlined.DocumentScanner, onOcr,
                    if (models.checking) stringResource(R.string.refine_checking) else null)
            }
            if (settings.translatorEngine in offlineTranslationEngines && (needsModels || expanded)) ReadinessRow(R.string.setup_models,
                if (models.checking) null else models.translationReady, true, Icons.Outlined.Download, onModels,
                if (models.checking) stringResource(R.string.refine_checking) else null)
            TextButton(onClick = { expanded = !expanded }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(if (expanded) R.string.polish_less else R.string.polish_readiness_details))
                Icon(if (expanded) Icons.Outlined.ExpandLess else Icons.Outlined.ExpandMore, null)
            }
            if (expanded) {
                HorizontalDivider(Modifier.padding(vertical = 12.dp))
                ReadinessRow(R.string.refine_capture_ready, null, false, Icons.Outlined.CropFree, onCapture, stringResource(R.string.refine_on_start))
                ReadinessRow(R.string.setup_accessibility, accessibility, false, Icons.Outlined.Accessibility, onAccessibility)
                ReadinessRow(R.string.setup_notifications, notifications, false, Icons.Outlined.Notifications, onNotifications)
                ReadinessRow(R.string.setup_battery, battery, false, Icons.Outlined.BatterySaver, onBattery)
            }
        }
    }
}

@Composable
private fun ReadinessRow(title: Int, ready: Boolean?, required: Boolean, icon: ImageVector, onClick: () -> Unit, summary: String? = null) {
    Surface(onClick = onClick, color = androidx.compose.ui.graphics.Color.Transparent, shape = MaterialTheme.shapes.small) {
        Row(Modifier.fillMaxWidth().heightIn(min = 64.dp).padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(if (ready == true) Icons.Outlined.CheckCircle else icon, null,
                tint = if (ready == false && required) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(stringResource(title), style = MaterialTheme.typography.bodyMedium)
                Text(summary ?: stringResource(if (ready == true) R.string.refine_enabled else if (required) R.string.refine_required else R.string.refine_optional),
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.AutoMirrored.Outlined.KeyboardArrowRight, null, Modifier.size(18.dp))
        }
    }
}
