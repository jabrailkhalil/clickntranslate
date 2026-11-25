// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.media.projection.MediaProjectionConfig
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.lifecycle.ViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.viewModelScope
import dev.clickn.translate.ui.MainActivity
import dev.clickn.translate.data.SettingsRepository
import dagger.hilt.android.AndroidEntryPoint
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

/** Shared transparent launch host, isolated from home so a tile tap preserves the foreground app. */
@AndroidEntryPoint
class CaptureStartRequestActivity : ComponentActivity() {
    private val viewModel: CaptureStartViewModel by viewModels()

    private val mpm by lazy {
        getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
    }

    private val launcher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            Timber.i("MediaProjection granted")
            viewModel.projectionGranted(result.resultCode, result.data!!)
        } else {
            Timber.w("MediaProjection denied")
            viewModel.projectionDenied()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        lifecycleScope.launch {
            viewModel.stage.collect { stage ->
                when (stage) {
                    CaptureStartStage.WAITING -> Unit
                    CaptureStartStage.PROJECTION -> if (viewModel.canPrepareProjection()) {
                        try {
                            // Nothing is marked externally launched during this cancellable await.
                            val fullScreen = viewModel.shouldShareEntireScreen()
                            currentCoroutineContext().ensureActive()
                            val intent = if (Build.VERSION.SDK_INT >= 34 && fullScreen) {
                                mpm.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay())
                            } else {
                                mpm.createScreenCaptureIntent()
                            }
                            if (viewModel.consumeProjectionRequest()) launcher.launch(intent)
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (error: Exception) {
                            permissionLaunchFailed(error)
                        }
                    }
                    CaptureStartStage.OVERLAY_PERMISSION -> {
                        if (viewModel.consumeOverlayRequest()) {
                            openOverlayPermissionSettings(this@CaptureStartRequestActivity)
                        }
                    }
                    CaptureStartStage.SETUP -> {
                        startActivity(Intent(this@CaptureStartRequestActivity, MainActivity::class.java)
                            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or
                                Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
                        finishRequest()
                    }
                    CaptureStartStage.FINISHED -> {
                        if (viewModel.consumeOverlayDeniedNotice()) {
                            Toast.makeText(dev.clickn.translate.data.AppLocalePrefs.live(this@CaptureStartRequestActivity),
                                dev.clickn.translate.R.string.capture_start_overlay_denied, Toast.LENGTH_LONG).show()
                        }
                        finishRequest()
                    }
                }
            }
        }
    }

    // Register in stable constructor order: projection first, overlay second. Only primitive
    // admission flags are saved here; ActivityResultRegistry owns pending platform results.
    private val overlayPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        viewModel.overlayPermissionReturned(Settings.canDrawOverlays(this))
    }

    private fun openOverlayPermissionSettings(context: Context) {
        try {
            overlayPermissionLauncher.launch(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${context.packageName}")))
        } catch (_: Exception) {
            try {
                overlayPermissionLauncher.launch(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION))
            } catch (error: Exception) { permissionLaunchFailed(error) }
        }
    }

    private fun permissionLaunchFailed(error: Exception) {
        Timber.w(error, "[capture-start] permission UI unavailable")
        Toast.makeText(dev.clickn.translate.data.AppLocalePrefs.live(this),
            dev.clickn.translate.R.string.capture_start_permission_unavailable, Toast.LENGTH_LONG).show()
        viewModel.permissionLaunchFailed()
    }

    private fun finishRequest() {
        // Finishing the whole task could also remove a newer request launched during teardown.
        if (!isFinishing) finish()
    }

    companion object {
        fun newIntent(context: Context): Intent =
            Intent(context, CaptureStartRequestActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_NO_ANIMATION)
            }
    }
}

enum class CaptureStartStage { WAITING, PROJECTION, OVERLAY_PERMISSION, SETUP, FINISHED }

@HiltViewModel
class CaptureStartViewModel @Inject constructor(
    private val coordinator: CaptureStartCoordinator,
    private val savedState: SavedStateHandle,
    private val settingsRepository: SettingsRepository,
) : ViewModel() {
    private val admission = CapturePermissionAdmission(CapturePermissionSnapshot(
        pending = savedState.get<String>("capturePendingPermission")?.let { name ->
            CapturePendingPermission.entries.firstOrNull { it.name == name } ?: CapturePendingPermission.FINISHED
        } ?: if (savedState.get<Boolean>("projectionRequested") == true) CapturePendingPermission.PROJECTION
            else CapturePendingPermission.NONE,
        overlayAttempted = savedState.get<Boolean>("captureOverlayAttempted") == true,
        overlayDeniedNotice = savedState.get<Boolean>("captureOverlayDeniedNotice") == true,
    ))
    private val ownsGate = coordinator.gate.acquire(admission)
    private val currentStage = MutableStateFlow(when (admission.snapshot.pending) {
        CapturePendingPermission.NONE -> CaptureStartStage.WAITING
        CapturePendingPermission.OVERLAY -> CaptureStartStage.OVERLAY_PERMISSION
        CapturePendingPermission.PROJECTION -> CaptureStartStage.PROJECTION
        CapturePendingPermission.FINISHED -> CaptureStartStage.FINISHED
    })
    val stage = currentStage.asStateFlow()

    init {
        if (!ownsGate) finishAdmission()
        else if (admission.snapshot.pending == CapturePendingPermission.NONE) prepare()
    }

    private fun prepare() {
        viewModelScope.launch {
            if (!ownsGate || admission.snapshot.pending != CapturePendingPermission.NONE) return@launch
            try {
                val decision = coordinator.prepare()
                currentCoroutineContext().ensureActive()
                if (admission.snapshot.pending != CapturePendingPermission.NONE) return@launch
                when (decision) {
                    CaptureStartDecision.AlreadyRunning -> finishAdmission()
                    CaptureStartDecision.OpenSetup -> {
                        admission.finish()
                        saveAdmission()
                        currentStage.value = CaptureStartStage.SETUP
                    }
                    CaptureStartDecision.OpenOverlaySettings -> {
                        if (admission.snapshot.overlayAttempted) {
                            admission.finishOverlayDenied()
                            saveAdmission()
                            currentStage.value = CaptureStartStage.FINISHED
                        } else currentStage.value = CaptureStartStage.OVERLAY_PERMISSION
                    }
                    is CaptureStartDecision.Ready -> {
                        if (decision.backend == CaptureBackend.MEDIA_PROJECTION) {
                            currentStage.value = CaptureStartStage.PROJECTION
                        } else {
                            finishAdmission()
                            coordinator.start(decision.backend)
                        }
                    }
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: Exception) {
                Timber.w(error, "[capture-start] prepare failed")
                admission.finish()
                saveAdmission()
                currentStage.value = CaptureStartStage.SETUP
            }
        }
    }

    fun canPrepareProjection(): Boolean = ownsGate && currentStage.value == CaptureStartStage.PROJECTION &&
        admission.snapshot.pending == CapturePendingPermission.NONE

    fun consumeProjectionRequest(): Boolean {
        if (!canPrepareProjection() || !admission.beginProjection()) return false
        savedState["projectionRequested"] = true
        saveAdmission()
        return true
    }

    fun consumeOverlayRequest(): Boolean {
        if (!ownsGate || currentStage.value != CaptureStartStage.OVERLAY_PERMISSION || !admission.beginOverlay()) return false
        saveAdmission()
        return true
    }

    fun overlayPermissionReturned(granted: Boolean) {
        if (!ownsGate || !admission.consumeOverlayResult(granted)) return
        saveAdmission()
        if (granted) {
            currentStage.value = CaptureStartStage.WAITING
            prepare()
        } else currentStage.value = CaptureStartStage.FINISHED
    }

    fun consumeOverlayDeniedNotice(): Boolean = admission.consumeDeniedNotice().also { saveAdmission() }

    fun permissionLaunchFailed() = finishAdmission()

    fun projectionDenied() {
        if (!ownsGate || !admission.consumeProjectionResult()) return
        // The underlying Activity can be interactive before this permission host is destroyed.
        coordinator.gate.release(admission)
        saveAdmission()
        currentStage.value = CaptureStartStage.FINISHED
    }

    suspend fun shouldShareEntireScreen(): Boolean {
        val settings = settingsRepository.get()
        return shouldRequestEntireScreen(
            Build.VERSION.SDK_INT, settings.developerOptionsEnabled, settings.shareEntireScreen,
        )
    }

    fun projectionGranted(code: Int, data: Intent) {
        if (!ownsGate || !admission.consumeProjectionResult()) return
        saveAdmission()
        currentStage.value = CaptureStartStage.FINISHED
        try {
            coordinator.start(CaptureBackend.MEDIA_PROJECTION, code, data)
        } catch (error: Exception) {
            Timber.w(error, "[capture-start] projection startup failed")
        }
    }

    private fun saveAdmission() {
        savedState["capturePendingPermission"] = admission.snapshot.pending.name
        savedState["captureOverlayAttempted"] = admission.snapshot.overlayAttempted
        savedState["captureOverlayDeniedNotice"] = admission.snapshot.overlayDeniedNotice
        savedState["projectionRequested"] = admission.snapshot.pending == CapturePendingPermission.PROJECTION
    }

    private fun finishAdmission() {
        admission.finish()
        saveAdmission()
        currentStage.value = CaptureStartStage.FINISHED
    }

    override fun onCleared() {
        admission.finish()
        // An outgoing host can finish after another host has already claimed the gate.
        coordinator.gate.release(admission)
    }
}

internal enum class CapturePendingPermission { NONE, OVERLAY, PROJECTION, FINISHED }

internal data class CapturePermissionSnapshot(
    val pending: CapturePendingPermission = CapturePendingPermission.NONE,
    val overlayAttempted: Boolean = false,
    val overlayDeniedNotice: Boolean = false,
)

/** Single-use external admission; snapshot contains no Intent, projection token or settings. */
internal class CapturePermissionAdmission(initial: CapturePermissionSnapshot = CapturePermissionSnapshot()) {
    var snapshot = initial
        private set

    fun beginOverlay(): Boolean {
        if (snapshot.pending != CapturePendingPermission.NONE || snapshot.overlayAttempted) return false
        snapshot = snapshot.copy(pending = CapturePendingPermission.OVERLAY, overlayAttempted = true)
        return true
    }

    fun consumeOverlayResult(granted: Boolean): Boolean {
        if (snapshot.pending != CapturePendingPermission.OVERLAY) return false
        snapshot = snapshot.copy(pending = if (granted) CapturePendingPermission.NONE else CapturePendingPermission.FINISHED,
            overlayDeniedNotice = !granted)
        return true
    }

    fun beginProjection(): Boolean {
        if (snapshot.pending != CapturePendingPermission.NONE) return false
        snapshot = snapshot.copy(pending = CapturePendingPermission.PROJECTION)
        return true
    }

    fun consumeProjectionResult(): Boolean {
        if (snapshot.pending != CapturePendingPermission.PROJECTION) return false
        finish()
        return true
    }

    fun finishOverlayDenied() {
        snapshot = snapshot.copy(pending = CapturePendingPermission.FINISHED, overlayDeniedNotice = true)
    }

    fun consumeDeniedNotice(): Boolean = snapshot.overlayDeniedNotice.also {
        snapshot = snapshot.copy(overlayDeniedNotice = false)
    }

    fun finish() { snapshot = snapshot.copy(pending = CapturePendingPermission.FINISHED) }
}
