package dev.clickn.translate.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Share
import androidx.compose.material3.Icon
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

/** The same copy/share behaviour for a live result and an already saved translation. */
@Composable
internal fun TextOutputActions(text: String, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
    var copied by remember(text) { mutableStateOf(false) }
    FlowRow(modifier, horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        TextButton(onClick = {
            clipboard?.setPrimaryClip(ClipData.newPlainText(AppBrand.DISPLAY_NAME, text))
            copied = clipboard != null
        }, contentPadding = PaddingValues(horizontal = 8.dp)) {
            Icon(Icons.Outlined.ContentCopy, null, Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text(stringResource(if (copied) R.string.mobile_copied else R.string.mobile_copy))
        }
        TextButton(onClick = {
            context.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, text)
            }, null))
        }, contentPadding = PaddingValues(horizontal = 8.dp)) {
            Icon(Icons.Outlined.Share, null, Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.mobile_share))
        }
    }
}
