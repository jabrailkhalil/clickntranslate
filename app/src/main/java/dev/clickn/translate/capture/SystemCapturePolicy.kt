// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import dev.clickn.translate.shizuku.ShizukuCapabilities
import java.util.concurrent.atomic.AtomicBoolean

enum class CaptureStartMode { SYSTEM, SHIZUKU }
enum class CaptureBackend { ACCESSIBILITY, MEDIA_PROJECTION, SHIZUKU }

internal fun resolveCaptureStartMode(
    preferred: CaptureStartMode?, availability: ShizukuCapabilities.Availability,
): CaptureStartMode = preferred ?: CaptureStartMode.SYSTEM

/** Showing a start action is not proof that the overlay permission has been granted. */
internal fun showCaptureStartControls(
    overlayPermissionGranted: Boolean,
    serviceRunning: Boolean,
    availability: ShizukuCapabilities.Availability,
): Boolean = serviceRunning || overlayPermissionGranted ||
    availability == ShizukuCapabilities.Availability.READY

internal fun systemCaptureBackend(sdk: Int, connected: Boolean, capable: Boolean): CaptureBackend =
    if (sdk >= 30 && connected && capable) CaptureBackend.ACCESSIBILITY
    else CaptureBackend.MEDIA_PROJECTION

internal class CaptureStartGate {
    private val busy = AtomicBoolean(false)
    fun acquire(): Boolean = busy.compareAndSet(false, true)
    fun release() { busy.set(false) }
}

/** AOSP rejects requests <=333 ms apart. Shared by every screenshotter instance. */
internal class AccessibilityScreenshotPacing(private val intervalMs: Long = 350L) {
    private var lastRequestMs: Long? = null
    fun delayBeforeRequest(nowMs: Long): Long = lastRequestMs?.let {
        if (nowMs < it) 0L else (intervalMs - (nowMs - it)).coerceAtLeast(0L)
    } ?: 0L
    fun requestStarted(nowMs: Long) { lastRequestMs = nowMs }
}
