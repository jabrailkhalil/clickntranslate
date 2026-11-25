// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.app.StatusBarManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.drawable.Icon
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.widget.Toast
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartRequestActivity
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

@AndroidEntryPoint
class CaptureQuickSettingsTileService : TileService() {

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var stateJob: Job? = null

    override fun onStartListening() {
        super.onStartListening()
        stateJob?.cancel()
        stateJob = serviceScope.launch {
            CaptureServiceState.running.collectLatest(::updateTileState)
        }
    }

    override fun onStopListening() {
        stateJob?.cancel()
        stateJob = null
        super.onStopListening()
    }

    override fun onDestroy() {
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onClick() {
        super.onClick()
        val action = resolveCaptureQuickSettingsAction(
            serviceRunning = CaptureServiceState.running.value,
        )
        if (action == CaptureQuickSettingsAction.STOP_SERVICE) {
            runCatching { startService(CaptureService.stopIntent(this)) }
                .onFailure { showLaunchFailure() }
            return
        }
        val startAction = Runnable {
            // Unlock may have taken seconds. Never stop an independently started session here.
            if (!CaptureServiceState.running.value) performStartAction(action)
        }
        if (isLocked) {
            unlockAndRun(startAction)
        } else {
            startAction.run()
        }
    }

    private fun performStartAction(action: CaptureQuickSettingsAction) {
        try { when (action) {
            CaptureQuickSettingsAction.STOP_SERVICE -> Unit
            CaptureQuickSettingsAction.REQUEST_START ->
                launchActivity(CaptureStartRequestActivity.newIntent(this), CAPTURE_START_REQUEST_CODE)
        } } catch (_: Exception) { showLaunchFailure() }
    }

    // The Intent overload is required below API 34; newer devices use PendingIntent.
    @SuppressLint("StartActivityAndCollapseDeprecated")
    private fun launchActivity(intent: Intent, requestCode: Int) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            val pendingIntent = PendingIntent.getActivity(
                this,
                requestCode,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            startActivityAndCollapse(pendingIntent)
        } else {
            @Suppress("DEPRECATION")
            startActivityAndCollapse(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }

    private fun updateTileState(running: Boolean) {
        val localized = dev.clickn.translate.data.AppLocalePrefs.live(this)
        val actionLabel = localized.getString(if (running) R.string.integration_tile_stop else R.string.integration_tile_start)
        qsTile?.apply {
            state = if (running) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE
            label = getString(R.string.quick_settings_tile_label)
            contentDescription = "$label. $actionLabel"
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) subtitle = actionLabel
            updateTile()
        }
    }

    private fun showLaunchFailure() {
        val localized = dev.clickn.translate.data.AppLocalePrefs.live(this)
        Toast.makeText(localized, R.string.integration_tile_launch_failed, Toast.LENGTH_LONG).show()
        updateTileState(CaptureServiceState.running.value)
    }

    companion object {
        private const val CAPTURE_START_REQUEST_CODE = 0x5142
        private const val QUICK_SETTINGS_SETTINGS_ACTION = "android.settings.QUICK_SETTINGS_SETTINGS"

        fun requestAdd(context: Context) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                val statusBarManager = context.getSystemService(StatusBarManager::class.java)
                val requested = runCatching {
                    statusBarManager.requestAddTileService(
                        ComponentName(context, CaptureQuickSettingsTileService::class.java),
                        context.getString(R.string.quick_settings_tile_label),
                        Icon.createWithResource(context, R.drawable.ic_menu_full_screen),
                        context.mainExecutor,
                    ) { }
                }.isSuccess
                if (requested) return
            }
            val opened = runCatching {
                context.startActivity(
                    Intent(QUICK_SETTINGS_SETTINGS_ACTION)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            }.isSuccess
            if (!opened) {
                context.startActivity(
                    Intent(android.provider.Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            }
        }
    }
}
