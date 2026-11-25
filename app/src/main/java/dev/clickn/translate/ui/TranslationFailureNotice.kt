package dev.clickn.translate.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import dev.clickn.translate.AppBrand
import dev.clickn.translate.R
import dev.clickn.translate.translate.TranslationFailureDescriptor
import dev.clickn.translate.translate.TranslationFailureKind

/** No messages, URLs, headers, request/response text or credentials are exposed in these details. */
@Composable
internal fun TranslationFailureNotice(failure: TranslationFailureDescriptor, onRetry: () -> Unit, onProvider: () -> Unit,
    retryEnabled: Boolean = true) {
    var details by remember(failure) { mutableStateOf(false) }
    val message = when (failure.kind) {
        TranslationFailureKind.OFFLINE -> R.string.mobile_failure_connection
        TranslationFailureKind.TIMEOUT -> R.string.mobile_failure_timeout
        TranslationFailureKind.AUTH -> R.string.mobile_failure_access
        TranslationFailureKind.RATE_LIMIT -> R.string.mobile_failure_limit
        TranslationFailureKind.TLS -> R.string.mobile_failure_tls
        TranslationFailureKind.SERVICE -> R.string.mobile_failure_service
        TranslationFailureKind.INVALID_RESPONSE -> R.string.mobile_failure_response
        TranslationFailureKind.UNKNOWN -> R.string.mobile_error
    }
    Text(stringResource(message), Modifier.padding(top = 16.dp), style = MaterialTheme.typography.bodyLarge,
        color = MaterialTheme.colorScheme.error)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        TextButton(onClick = onRetry, enabled = retryEnabled) { Text(stringResource(R.string.mobile_try_again)) }
        TextButton(onClick = onProvider) { Text(stringResource(R.string.mobile_configure)) }
        TextButton(onClick = { details = true }) { Text(stringResource(R.string.mobile_failure_details)) }
    }
    if (details) {
        val context = LocalContext.current
        val diagnostic = remember(failure) {
            buildString {
                append(failure.diagnosticCode)
                if (failure.causeTypes.isNotEmpty()) append("\n" + failure.causeTypes.joinToString(" → "))
                if (failure.causeCycle) append("\nCAUSE_CYCLE")
                if (failure.chainTruncated) append("\nCAUSE_CHAIN_TRUNCATED")
            }
        }
        var copied by remember(failure) { mutableStateOf(false) }
        AlertDialog(onDismissRequest = { details = false },
            title = { Text(stringResource(R.string.mobile_failure_details)) },
            text = {
                Column {
                    Text(stringResource(R.string.mobile_failure_details_body))
                    SelectionContainer { Text(diagnostic, Modifier.padding(top = 16.dp)) }
                }
            },
            confirmButton = { TextButton(onClick = { details = false }) { Text(stringResource(R.string.mobile_history_close)) } },
            dismissButton = { TextButton(onClick = {
                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                clipboard?.setPrimaryClip(ClipData.newPlainText(AppBrand.DISPLAY_NAME, diagnostic))
                copied = clipboard != null
            }) { Text(stringResource(if (copied) R.string.mobile_copied else R.string.mobile_copy)) } },
        )
    }
}
