// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.shizuku

import android.content.Context
import android.os.Process
import android.provider.Settings
import dev.clickn.translate.trigger.AccessibilityServiceStatus
import dev.clickn.translate.trigger.ClickTranslateAccessibilityService
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import timber.log.Timber

/** Explicit user action only. No Binder listener or background auto-reenable. */
@Singleton
class AppPermissionCoordinator @Inject constructor(
    @ApplicationContext private val context: Context,
    private val shizuku: ShizukuManager,
) {
    private val mutex = Mutex()

    suspend fun configure(): AppPermissionResult = configure(requireAlreadyReady = false)

    /** Manual accessibility entries must open Settings immediately if Shizuku is not ready. */
    suspend fun configureIfReady(): AppPermissionResult {
        // Do not wait behind another grant operation when Shizuku is already unavailable.
        if (!hasReadyShizuku()) return currentState().result()
        return configure(requireAlreadyReady = true)
    }

    private fun hasReadyShizuku() =
        shizuku.isServiceRunning() && shizuku.hasPermission() && shizuku.shellPrivilegeOk.value

    private suspend fun configure(requireAlreadyReady: Boolean): AppPermissionResult = mutex.withLock {
        val userId = Process.myUid() / 100_000
        prepareMissingAppPermissions(
            readState = ::currentState,
            ensureShizukuReady = {
                if (requireAlreadyReady) {
                    shizuku.verifyShellPrivilegeAsync()
                    hasReadyShizuku()
                } else {
                    shizuku.ensureReady()
                }
            },
            grantOverlay = {
                shizuku.grantOverlayPermission(context.packageName, userId.toString())
            },
            enableAccessibility = {
                val previous = shizuku.executeSettingsCommand(accessibilitySettingsCommand(userId))
                if (previous != null) {
                    val merged = withAccessibilityService(previous, context.packageName,
                        ClickTranslateAccessibilityService::class.java.name)
                    shizuku.executeSettingsCommand(accessibilitySettingsCommand(userId, merged)) != null
                } else {
                    false
                }
            },
        ).also {
            Timber.i("[shizuku-permissions] overlay=%s accessibilityConnected=%s",
                it.overlayGranted, it.accessibilityConnected)
        }
    }

    internal fun currentState() = AppPermissionState(
        overlayGranted = Settings.canDrawOverlays(context),
        accessibilityEnabled = AccessibilityServiceStatus.isEnabled(context),
        accessibilityConnected = ClickTranslateAccessibilityService.isConnected(),
    )
}
