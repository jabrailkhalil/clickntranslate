// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.core.content.ContextCompat
import dev.clickn.translate.download.shouldRequestModelDownloadNotificationPermission

@Composable
internal fun rememberModelDownloadNotificationPermissionGate(): ((() -> Unit) -> Unit) {
    val context = LocalContext.current
    var pendingDownload by remember { mutableStateOf<(() -> Unit)?>(null) }
    val launcher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) {
        val download = pendingDownload
        pendingDownload = null
        download?.invoke()
    }

    return { onConfirmed ->
        val permissionGranted = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        if (shouldRequestModelDownloadNotificationPermission(
                sdkInt = Build.VERSION.SDK_INT,
                permissionGranted = permissionGranted,
            )
        ) {
            pendingDownload = onConfirmed
            launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            onConfirmed()
        }
    }
}
