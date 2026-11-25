package dev.clickn.translate.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.R
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.history.TextHistoryEntry
import java.text.DateFormat
import java.util.Date

/** Reading, selecting, copying and sharing a saved result never starts translation. */
@Composable
internal fun HistoryEntryDialog(entry: TextHistoryEntry, onDismiss: () -> Unit, onUseSource: () -> Unit) {
    val locale = LocalContext.current.resources.configuration.locales[0]
    val maximumTextHeight = (LocalConfiguration.current.screenHeightDp * 0.45f).dp
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.mobile_history_entry_title)) },
        text = {
            Column(Modifier.fillMaxWidth()) {
                Text("${languageName(entry.from)} → ${languageName(entry.to)}",
                    style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                Text(DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT, locale).format(Date(entry.createdAtMs)),
                    style = MaterialTheme.typography.labelSmall)
                TranslatorEngine.entries.firstOrNull { it.name == entry.provider }?.let {
                    Text(providerName(it), style = MaterialTheme.typography.labelSmall)
                }
                TextOutputActions(entry.translated)
                HorizontalDivider()
                Column(Modifier.fillMaxWidth().heightIn(max = maximumTextHeight).verticalScroll(rememberScrollState())) {
                    Spacer(Modifier.height(16.dp))
                    Text(stringResource(R.string.mobile_history_original), style = MaterialTheme.typography.labelLarge)
                    SelectionContainer { Text(entry.source, style = MaterialTheme.typography.bodyLarge) }
                    Spacer(Modifier.height(20.dp))
                    Text(stringResource(R.string.mobile_result), style = MaterialTheme.typography.labelLarge)
                    SelectionContainer { Text(entry.translated, style = MaterialTheme.typography.bodyLarge) }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.mobile_history_close)) } },
        dismissButton = { TextButton(onClick = onUseSource) { Text(stringResource(R.string.mobile_history_use_source)) } },
    )
}
