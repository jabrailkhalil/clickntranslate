package dev.clickn.translate.update

import android.content.Context
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.work.Constraints
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.await
import androidx.work.workDataOf
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import dev.clickn.translate.AppBrand
import dev.clickn.translate.BuildConfig
import dev.clickn.translate.R
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.firstOrNull
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.util.UUID
import javax.inject.Inject

@Serializable
private data class PendingUpdate(val id: String, val apk: ReleaseApk, val installedCode: Int)

/** Claim the visible offer before WorkManager starts inserting the request. A second tap must not observe an uncommitted id. */
internal fun MutableStateFlow<UpdateViewModel.State>.claimUpdateDownload(apk: ReleaseApk): Boolean {
    val offer = value as? UpdateViewModel.State.Loaded ?: return false
    return offer.info.apk == apk && compareAndSet(offer, UpdateViewModel.State.Downloading(apk, 0))
}

@HiltViewModel
class UpdateViewModel @Inject constructor(
    @ApplicationContext private val appContext: Context,
    private val checker: UpdateChecker, private val json: Json,
) : ViewModel() {
    sealed class State {
        data object Idle : State()
        data object Checking : State()
        data class Loaded(val info: UpdateInfo) : State()
        data class Failed(val errorMessage: String) : State()
        data class Downloading(val apk: ReleaseApk, val percent: Int) : State()
        data class Ready(val apk: ReleaseApk) : State()
    }

    private val prefs = appContext.getSharedPreferences("update_checker", Context.MODE_PRIVATE)
    private val work by lazy { WorkManager.getInstance(appContext) }
    private val _state = MutableStateFlow<State>(State.Idle)
    val state = _state.asStateFlow()
    private val _autoChecking = MutableStateFlow(false)
    val autoChecking = _autoChecking.asStateFlow()
    private val _transfer = MutableStateFlow<State?>(null)
    val transfer = _transfer.asStateFlow()
    private var observer: Job? = null
    private var lookup: Job? = null
    private var dialogOpen = false
    private var announceNewRelease = false
    private var record: PendingUpdate? = null
    private var installing = false

    init {
        saved()?.let { pending ->
            if (pending.installedCode == BuildConfig.VERSION_CODE) watch(pending)
            else {
                forget(pending)
                viewModelScope.launch(Dispatchers.IO) { verifiedApkFile(appContext, pending.apk).delete() }
            }
        }
    }

    private fun saved() = prefs.getString("apk_job", null)?.let { value ->
        runCatching { json.decodeFromString<PendingUpdate>(value) }
            .getOrNull()?.takeIf { it.installedCode > 0 && it.apk.isValid() && runCatching { UUID.fromString(it.id) }.isSuccess }
    }

    fun check() {
        if (!AppBrand.updatesEnabled) return
        dialogOpen = true
        _transfer.value?.let { _state.value = it; return }
        _state.value = State.Checking
        if (lookup?.isActive != true) checkFeed()
    }

    fun autoCheckIfDue() {
        if (!AppBrand.updatesEnabled || lookup?.isActive == true || record != null || _state.value != State.Idle) return
        val now = System.currentTimeMillis()
        if (now - prefs.getLong("last_check_ms", 0L) in 0 until 60L * 60 * 1000) return
        prefs.edit().putLong("last_check_ms", now).apply()
        _autoChecking.value = true
        announceNewRelease = true
        checkFeed()
    }

    private fun checkFeed() {
        lookup = viewModelScope.launch {
            try {
                var info = checker.checkLatest()
                if (info.compareBuild) {
                    if (!dialogOpen) return@launch
                    if (checker.sameInstalledBuild(requireNotNull(info.apk)))
                        info = UpdateInfo(BuildConfig.VERSION_NAME, BuildConfig.VERSION_NAME, null)
                }
                val skipped = prefs.getString("skipped_version", null)
                if (dialogOpen || (announceNewRelease && info.hasUpdate && !info.compareBuild && skipped != info.latestVersion)) {
                    dialogOpen = true
                    _state.value = State.Loaded(info)
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (dialogOpen) _state.value = State.Failed(appContext.getString(R.string.update_dialog_failed_format, error.message.orEmpty()))
            } finally {
                _autoChecking.value = false
                announceNewRelease = false
            }
        }
    }

    fun skipVersion(version: String) {
        when (val visible = _state.value) {
            is State.Loaded -> if (visible.info.apk?.version != version) return
            is State.Ready -> {
                if (visible.apk.version != version) return
                record?.takeIf { it.apk == visible.apk }?.let(::forget)
            }
            else -> return
        }
        prefs.edit().putString("skipped_version", version).apply()
        reset()
    }

    fun retry() {
        record?.takeIf { _transfer.value is State.Failed }?.let { watch(it); return }
        if (_transfer.value is State.Failed) _transfer.value = null
        check()
    }

    fun reset() {
        dialogOpen = false
        announceNewRelease = false
        _state.value = State.Idle
    }

    fun download(apk: ReleaseApk) {
        if (!AppBrand.updatesEnabled || !apk.isValid() || !_state.claimUpdateDownload(apk)) return
        dialogOpen = true
        saved()?.let { watch(it); return }
        val request = OneTimeWorkRequestBuilder<ApkUpdateWorker>()
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setInputData(workDataOf(ApkUpdateWorker.APK to json.encodeToString(apk))).build()
        val pending = PendingUpdate(request.id.toString(), apk, BuildConfig.VERSION_CODE)
        record = pending
        prefs.edit().putString("apk_job", json.encodeToString(pending)).apply()
        publish(State.Downloading(apk, 0))
        viewModelScope.launch {
            try {
                // A missing preference can leave an orphan in WorkManager after process death.
                work.enqueueUniqueWork(ApkUpdateWorker.WORK_NAME, ExistingWorkPolicy.REPLACE, request).await()
                if (record == pending) watch(pending)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (record == pending) fail(pending, R.string.update_download_failed)
            }
        }
    }

    private fun watch(pending: PendingUpdate) {
        record = pending
        publish(State.Downloading(pending.apk, 0))
        observer?.cancel()
        observer = viewModelScope.launch {
            work.getWorkInfoByIdFlow(UUID.fromString(pending.id)).catch {
                if (record == pending) publish(State.Failed(appContext.getString(R.string.update_download_failed)))
            }.firstOrNull { info ->
                if (record != pending) return@firstOrNull true
                when (info?.state) {
                    WorkInfo.State.ENQUEUED, WorkInfo.State.BLOCKED, WorkInfo.State.RUNNING ->
                        publish(State.Downloading(pending.apk, info.progress.getInt(ApkUpdateWorker.PROGRESS, 0)))
                    WorkInfo.State.SUCCEEDED -> {
                        if (info.outputData.getBoolean(ApkUpdateWorker.CURRENT, false)) {
                            forget(pending)
                            if (dialogOpen) _state.value = State.Loaded(UpdateInfo(BuildConfig.VERSION_NAME, BuildConfig.VERSION_NAME, null))
                        } else if (verifiedApkFile(appContext, pending.apk).isFile) publish(State.Ready(pending.apk))
                        else fail(pending, R.string.update_download_failed)
                    }
                    WorkInfo.State.FAILED -> fail(pending, if (info.outputData.getBoolean(ApkUpdateWorker.INVALID, false))
                        R.string.update_invalid_apk else R.string.update_download_failed)
                    WorkInfo.State.CANCELLED, null -> { forget(pending); if (dialogOpen) reset() }
                }
                info == null || info.state.isFinished
            }
        }
    }

    fun cancelDownload() {
        val pending = record ?: return
        if (_transfer.value !is State.Downloading) return
        observer?.cancel()
        // Keep the persisted job until WorkManager acknowledges cancellation.
        viewModelScope.launch {
            try {
                work.cancelWorkById(UUID.fromString(pending.id)).await()
                if (record == pending) { forget(pending); reset() }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                if (record == pending) watch(pending)
            }
        }
    }

    fun install(apk: ReleaseApk, launchInstaller: (Intent) -> Unit) {
        val pending = record ?: return
        if (pending.apk != apk || _state.value !is State.Ready || installing) return
        installing = true
        viewModelScope.launch {
            try {
                val intent = withContext(Dispatchers.IO) { verifiedInstallerIntent(appContext, apk) }
                if (dialogOpen && _state.value == State.Ready(apk)) { launchInstaller(intent); reset() }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (error is InvalidApk) fail(pending, R.string.update_invalid_apk)
                else if (dialogOpen) _state.value = State.Failed(appContext.getString(R.string.update_install_failed))
            } finally {
                installing = false
            }
        }
    }

    private fun publish(state: State) {
        _transfer.value = state
        if (dialogOpen) _state.value = state
    }

    private fun fail(pending: PendingUpdate, reason: Int) {
        forget(pending)
        val failed = State.Failed(appContext.getString(reason))
        _transfer.value = if (dialogOpen) null else failed
        if (dialogOpen) _state.value = failed
    }

    private fun forget(pending: PendingUpdate) {
        if (saved()?.id == pending.id) prefs.edit().remove("apk_job").apply()
        record = null
        _transfer.value = null
    }
}
