// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

internal fun shouldRequestEntireScreen(
    sdkInt: Int,
    developerOptionsEnabled: Boolean,
    shareEntireScreen: Boolean,
): Boolean = sdkInt >= 34 && developerOptionsEnabled && shareEntireScreen
