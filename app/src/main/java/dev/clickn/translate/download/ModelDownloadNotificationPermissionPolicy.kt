// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.download

import android.os.Build

internal fun shouldRequestModelDownloadNotificationPermission(
    sdkInt: Int,
    permissionGranted: Boolean,
): Boolean = sdkInt >= Build.VERSION_CODES.TIRAMISU && !permissionGranted
