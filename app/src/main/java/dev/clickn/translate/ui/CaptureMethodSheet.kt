package dev.clickn.translate.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.annotation.StringRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import dev.clickn.translate.shizuku.ShizukuBackendPackage
import dev.clickn.translate.shizuku.ShizukuCapabilities

private const val SHIZUKU_SETUP_URL = "https://shizuku.rikka.app/guide/setup/"
private const val SHIZUKU_DOWNLOAD_URL = "https://shizuku.rikka.app/download/"

@Composable
internal fun CaptureMethodSheet(viewModel: MobileViewModel) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    val state by viewModel.shizukuState.collectAsState()
    val mode by CaptureStartPreference.mode.collectAsState()
    LaunchedEffect(viewModel) { viewModel.refreshShizuku() }
    DisposableEffect(lifecycle, viewModel) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.refreshShizuku()
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            viewModel.cancelShizukuPreparation()
        }
    }
    val canAuthorize = !state.checking && !state.authorizing && state.availability in setOf(
        ShizukuCapabilities.Availability.READY,
        ShizukuCapabilities.Availability.INSTALLED_NOT_GRANTED,
        ShizukuCapabilities.Availability.INSTALLED_NOT_PAIRED,
    )
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState())
        .navigationBarsPadding().padding(horizontal = 24.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.setup_capture), style = MaterialTheme.typography.headlineSmall)
        Text(stringResource(R.string.shizuku_start_intro), color = MaterialTheme.colorScheme.onSurfaceVariant)
        ListItem(
            headlineContent = { Text(stringResource(R.string.main_capture_system)) },
            supportingContent = { Text(stringResource(R.string.shizuku_start_system_body)) },
            trailingContent = { RadioButton(selected = mode != CaptureStartMode.SHIZUKU,
                onClick = viewModel::selectSystemCapture) },
            modifier = Modifier.clickable(onClick = viewModel::selectSystemCapture),
        )
        ListItem(
            headlineContent = { Text("Shizuku") },
            supportingContent = { Text(stringResource(R.string.shizuku_start_body)) },
            trailingContent = { RadioButton(selected = mode == CaptureStartMode.SHIZUKU,
                enabled = canAuthorize, onClick = viewModel::prepareShizuku) },
            modifier = Modifier.clickable(enabled = canAuthorize, onClick = viewModel::prepareShizuku),
        )
        Text(stringResource(if (state.checking) R.string.shizuku_start_checking
            else shizukuAvailabilityLabel(state.availability)),
            color = if (!state.checking && state.availability == ShizukuCapabilities.Availability.READY)
                MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
        if (state.checking || state.authorizing) LinearProgressIndicator(Modifier.fillMaxWidth())
        if (state.authorizing) {
            Text(stringResource(R.string.shizuku_start_authorizing))
            OutlinedButton(onClick = viewModel::cancelShizukuPreparation, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.shizuku_start_cancel))
            }
        } else if (canAuthorize) {
            Button(onClick = viewModel::prepareShizuku, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.shizuku_start_authorize))
            }
        }
        if (state.authorizationDenied) Text(stringResource(R.string.shizuku_start_not_confirmed),
            color = MaterialTheme.colorScheme.error)
        OutlinedButton(onClick = { openShizukuManagerOrHelp(context,
            install = state.availability == ShizukuCapabilities.Availability.NOT_INSTALLED) },
            modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(if (state.availability == ShizukuCapabilities.Availability.NOT_INSTALLED)
                R.string.shizuku_start_install else R.string.shizuku_start_open))
        }
        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)) {
            TextButton(onClick = { openSetupAndroidSettings(context,
                Intent(Intent.ACTION_VIEW, Uri.parse(SHIZUKU_SETUP_URL))) }) {
                Text(stringResource(R.string.shizuku_start_guide))
            }
            TextButton(onClick = viewModel::refreshShizuku, enabled = !state.checking && !state.authorizing) {
                Text(stringResource(R.string.shizuku_start_refresh))
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@StringRes
internal fun shizukuAvailabilityLabel(availability: ShizukuCapabilities.Availability): Int = when (availability) {
    ShizukuCapabilities.Availability.READY -> R.string.shizuku_start_ready
    ShizukuCapabilities.Availability.INSTALLED_NOT_GRANTED -> R.string.shizuku_start_permission
    ShizukuCapabilities.Availability.INSTALLED_NOT_PAIRED -> R.string.shizuku_start_no_privilege
    ShizukuCapabilities.Availability.INSTALLED_COMPATIBILITY_REQUIRED -> R.string.shizuku_start_compatibility
    ShizukuCapabilities.Availability.NOT_INSTALLED -> R.string.shizuku_start_not_installed
    ShizukuCapabilities.Availability.NOT_RUNNING -> R.string.shizuku_start_not_running
}

private fun openShizukuManagerOrHelp(context: Context, install: Boolean) {
    val guide = Intent(Intent.ACTION_VIEW, Uri.parse(if (install) SHIZUKU_DOWNLOAD_URL else SHIZUKU_SETUP_URL))
    val manager = ShizukuBackendPackage.entries.firstNotNullOfOrNull { backend ->
        runCatching { context.packageManager.getLaunchIntentForPackage(backend.packageName) }.getOrNull()
    }
    openSetupAndroidSettings(context, manager ?: guide, guide)
}
