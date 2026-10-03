// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import kotlinx.serialization.Serializable

/** The orientation of the content inside a capture, independent of the host device orientation. */
@Serializable
enum class CaptureContentOrientation {
    AUTO,
    LANDSCAPE,
    PORTRAIT,
}
