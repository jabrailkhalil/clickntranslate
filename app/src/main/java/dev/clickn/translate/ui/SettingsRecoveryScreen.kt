package dev.clickn.translate.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.SettingsImportRecoveryState

/** Covers the app until its local stores are coherent; no recovery payload reaches the UI. */
@Composable
internal fun SettingsRecoveryScreen(state: SettingsImportRecoveryState, onRetry: () -> Unit) {
    val failed = state == SettingsImportRecoveryState.FAILED
    Surface(Modifier.fillMaxSize().testTag("settings-recovery")) {
        Column(
            Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.safeDrawing)
                .verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp, Alignment.CenterVertically),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                stringResource(if (failed) R.string.settings_import_recovery_failed else R.string.settings_import_recovering),
                style = MaterialTheme.typography.headlineSmall,
                textAlign = TextAlign.Center,
            )
            if (failed) {
                Text(stringResource(R.string.settings_import_recovery_help), textAlign = TextAlign.Center)
                Button(onClick = onRetry) { Text(stringResource(R.string.settings_import_recovery_retry)) }
            } else {
                CircularProgressIndicator()
            }
        }
    }
}
