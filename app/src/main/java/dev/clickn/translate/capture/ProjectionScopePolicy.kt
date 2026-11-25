// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

/** Normal API34+ capture mirrors the display; advanced mode may retain the system chooser. */
internal fun shouldRequestEntireScreen(
    sdkInt: Int,
    developerOptionsEnabled: Boolean,
    shareEntireScreen: Boolean,
): Boolean = sdkInt >= 34 && (!developerOptionsEnabled || shareEntireScreen)
