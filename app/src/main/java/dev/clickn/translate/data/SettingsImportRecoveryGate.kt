package dev.clickn.translate.data

import android.content.Context
import androidx.datastore.core.DataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex

/** Startup barrier only. It does not claim live multi-store Flow snapshot isolation. */
enum class SettingsImportRecoveryState { READY, RECOVERING, FAILED }

@Singleton
class SettingsImportRecoveryGate private constructor(pending: Boolean) {
    @Inject constructor(@ApplicationContext context: Context) : this(
        SettingsImportJournal.hasRecord(File(context.noBackupFilesDir, SettingsImportJournal.DIRECTORY)),
    )

    @Volatile private var ready = CompletableDeferred<Unit>().also { if (!pending) it.complete(Unit) }
    private val mutableState = MutableStateFlow(if (pending) SettingsImportRecoveryState.RECOVERING else SettingsImportRecoveryState.READY)
    val state: StateFlow<SettingsImportRecoveryState> = mutableState.asStateFlow()
    private var running: Any? = null
    private var recoveryGeneration = 0L
    private var applicationScope: CoroutineScope? = null
    private var recovery: (suspend () -> Unit)? = null

    @Synchronized
    internal fun start(scope: CoroutineScope, recover: suspend () -> Unit) {
        applicationScope = scope
        recovery = recover
        if (!isReady()) launchRecovery()
    }

    /** A failed attempt leaves readers suspended; the Main failure panel can retry safely. */
    @Synchronized
    fun retry() {
        if (mutableState.value == SettingsImportRecoveryState.FAILED) launchRecovery()
    }

    @Synchronized
    internal fun requireRecovery() {
        if (isReady()) ready = CompletableDeferred()
        recoveryGeneration++
        mutableState.value = SettingsImportRecoveryState.FAILED
    }

    private fun launchRecovery() {
        if (running != null) return
        val scope = applicationScope ?: return
        val recover = recovery ?: return
        val attempt = Any()
        val generation = recoveryGeneration
        running = attempt
        mutableState.value = SettingsImportRecoveryState.RECOVERING
        val job = scope.launch {
            try {
                recover()
                synchronized(this@SettingsImportRecoveryGate) {
                    if (running === attempt) {
                        running = null
                        // A new failure can invalidate an older in-flight recovery.
                        // Only a recovery of the current generation may open readers.
                        if (generation == recoveryGeneration) {
                            mutableState.value = SettingsImportRecoveryState.READY
                            ready.complete(Unit)
                        } else mutableState.value = SettingsImportRecoveryState.FAILED
                    }
                }
            } catch (failure: Throwable) {
                // No raw exception, credential, URL or journal payload enters public state/logs.
                synchronized(this@SettingsImportRecoveryGate) {
                    if (running === attempt) {
                        running = null
                        mutableState.value = SettingsImportRecoveryState.FAILED
                    }
                }
                if (failure is CancellationException) throw failure
            }
        }
        // A cancelled scope may never enter the launch body (including its catch).
        // Do not strand the gate in RECOVERING with a permanently busy retry flag.
        job.invokeOnCompletion {
            synchronized(this@SettingsImportRecoveryGate) {
                if (running === attempt) {
                    running = null
                    mutableState.value = SettingsImportRecoveryState.FAILED
                }
            }
        }
    }

    internal suspend fun awaitReady() {
        while (true) {
            val awaited = ready
            awaited.await()
            if (isReady() && awaited === ready) return
        }
    }
    internal fun isReady(): Boolean = mutableState.value == SettingsImportRecoveryState.READY

    internal suspend fun <T> withReadyLock(mutex: Mutex, action: suspend () -> T): T {
        while (true) {
            awaitReady()
            mutex.lock()
            // A queued import must not hold the very lock needed by recovery to open its gate.
            if (!isReady()) { mutex.unlock(); continue }
            try { return action() } finally { mutex.unlock() }
        }
    }

    @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
    internal fun <T> wrap(store: DataStore<T>): DataStore<T> = object : DataStore<T> {
        override val data: Flow<T> = state.flatMapLatest { status ->
            if (status == SettingsImportRecoveryState.READY) store.data else emptyFlow()
        }
        override suspend fun updateData(transform: suspend (t: T) -> T): T {
            while (true) {
                awaitReady()
                try {
                    return store.updateData { current ->
                        // Admission may have happened before a long DataStore queue.
                        // Never await the gate inside this transform: recovery needs
                        // this same actor to restore its raw settings snapshot.
                        if (!isReady()) throw QueuedWriteNeedsRecovery()
                        transform(current)
                    }
                } catch (_: QueuedWriteNeedsRecovery) {
                    currentCoroutineContext().ensureActive()
                }
            }
        }
    }

    internal companion object {
        fun readyForIsolatedStore(): SettingsImportRecoveryGate = SettingsImportRecoveryGate(false)
        fun pendingForTest(): SettingsImportRecoveryGate = SettingsImportRecoveryGate(true)
    }

    private class QueuedWriteNeedsRecovery : IllegalStateException("Settings import recovery is pending.")
}
