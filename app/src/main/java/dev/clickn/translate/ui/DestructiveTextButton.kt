// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable

@Composable
internal fun DestructiveTextButton(
    label: String,
    onClick: () -> Unit,
    enabled: Boolean = true,
) {
    TextButton(onClick = onClick, enabled = enabled) {
        Text(
            text = label,
            color = MaterialTheme.colorScheme.error.copy(alpha = if (enabled) 1f else 0.38f),
        )
    }
}
