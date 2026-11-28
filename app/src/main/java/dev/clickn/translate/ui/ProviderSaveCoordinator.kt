package dev.clickn.translate.ui

import dev.clickn.translate.R
import dev.clickn.translate.data.SecureSettingsUnavailableException
import dev.clickn.translate.data.Settings
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.async
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

internal enum class ProviderSaveStatus(val errorMessage: Int? = null) {
    IDLE, SAVING, FAILED(R.string.mobile_provider_save_error),
    KEYSTORE_UNAVAILABLE(R.string.settings_secure_storage_unavailable),
}

/** The activity's ViewModel retains the form across rotation. Draft credentials stay in memory. */
internal class ProviderEditSession(initial: Settings) {
    val draft = MutableStateFlow(initial)
    private val submission = MutableStateFlow<Submission?>(null)
    val pending = submission.asStateFlow()

    class Submission(val commit: Deferred<Boolean>, val openAdvanced: Boolean)

    fun submit(openAdvanced: Boolean, persist: () -> Deferred<Boolean>) {
        if (submission.value == null) submission.value = Submission(persist(), openAdvanced)
    }

    suspend fun finish(request: Submission, onSaved: (Boolean) -> Unit) {
        val saved = request.commit.await()
        currentCoroutineContext().ensureActive()
        if (submission.compareAndSet(request, null) && saved) onSaved(request.openAdvanced)
    }
}

/** The owner is the ViewModel, so a dismissed/recreated UI cannot cancel a durable commit. */
internal class ProviderSaveCoordinator(private val owner: CoroutineScope) {
    private val lock = Any()
    private val mutableStatus = MutableStateFlow(ProviderSaveStatus.IDLE)
    val status = mutableStatus.asStateFlow()
    private var active: Deferred<Boolean>? = null

    fun clearFailure() {
        val previous = mutableStatus.value
        if (previous.errorMessage != null) mutableStatus.compareAndSet(previous, ProviderSaveStatus.IDLE)
    }

    fun save(persist: suspend () -> Unit): Deferred<Boolean> = synchronized(lock) {
        active?.takeUnless { it.isCompleted }?.let { return@synchronized it }
        mutableStatus.value = ProviderSaveStatus.SAVING
        val operation = owner.async(start = CoroutineStart.LAZY) {
            try {
                persist()
                true
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: SecureSettingsUnavailableException) {
                mutableStatus.value = ProviderSaveStatus.KEYSTORE_UNAVAILABLE
                false
            } catch (_: Exception) {
                // The UI gets no exception, request URL or credential-bearing details.
                mutableStatus.value = ProviderSaveStatus.FAILED
                false
            }
        }
        active = operation
        operation.invokeOnCompletion {
            synchronized(lock) {
                if (active === operation) {
                    active = null
                    if (mutableStatus.value == ProviderSaveStatus.SAVING) {
                        mutableStatus.value = ProviderSaveStatus.IDLE
                    }
                }
            }
        }
        operation.start()
        operation
    }
}
