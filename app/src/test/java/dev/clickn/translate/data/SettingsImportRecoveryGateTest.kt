package dev.clickn.translate.data

import androidx.datastore.core.DataStore
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.emitAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.yield
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.junit.Assert.*
import org.junit.Test

class SettingsImportRecoveryGateTest {
    @Test fun queuedOrdinaryWriteRetriesOutsideTheStoreAfterRecoveryClosesItsGate() = runBlocking {
        val gate = SettingsImportRecoveryGate.readyForIsolatedStore()
        val actor = Mutex(locked = true)
        val firstAttemptFinished = CompletableDeferred<Unit>()
        var value = 10
        var transforms = 0
        val raw = object : DataStore<Int> {
            override val data: Flow<Int> = flow { emit(value) }
            override suspend fun updateData(transform: suspend (Int) -> Int): Int = actor.withLock {
                try { transform(value).also { value = it } }
                finally { firstAttemptFinished.complete(Unit) }
            }
        }
        val wrapped = gate.wrap(raw)
        val queued = async(start = CoroutineStart.UNDISPATCHED) {
            wrapped.updateData { transforms++; it + 1 }
        }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            gate.requireRecovery()
            actor.unlock()
            withTimeout(5_000) { firstAttemptFinished.await() }
            assertEquals(0, transforms)
            assertEquals(10, value)
            assertFalse(queued.isCompleted)
            gate.start(scope) { raw.updateData { 20 } }
            assertEquals(21, withTimeout(5_000) { queued.await() })
            assertEquals(1, transforms)
        } finally { queued.cancelAndJoin(); scope.cancel() }
    }

    @Test fun newlyRequiredRecoveryCannotBeClearedByAnOlderRunningAttempt() = runBlocking {
        val gate = SettingsImportRecoveryGate.pendingForTest()
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        var attempts = 0
        try {
            gate.start(scope) { if (++attempts == 1) { entered.complete(Unit); release.await() } }
            withTimeout(5_000) { entered.await() }
            val oldAttempt = scope.coroutineContext[Job]!!.children.single()
            gate.requireRecovery()
            release.complete(Unit)
            withTimeout(5_000) { oldAttempt.join() }
            assertEquals(SettingsImportRecoveryState.FAILED, gate.state.value)
            assertNull(withTimeoutOrNull(100) { gate.awaitReady() })
            gate.retry()
            withTimeout(5_000) { gate.awaitReady() }
            assertEquals(2, attempts)
        } finally { release.complete(Unit); scope.cancel() }
    }

    @Test fun cancellationBeforeRecoveryBodyStartsDoesNotLeaveRetryPermanentlyBusy() = runBlocking {
        val gate = SettingsImportRecoveryGate.pendingForTest()
        val cancelled = CoroutineScope(SupervisorJob() + Dispatchers.Default).also { it.cancel() }
        val active = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        var calls = 0
        try {
            gate.start(cancelled) { calls++ }
            withTimeout(5_000) { gate.state.first { it == SettingsImportRecoveryState.FAILED } }
            assertEquals(0, calls)
            gate.start(active) { calls++ }
            withTimeout(5_000) { gate.awaitReady() }
            assertEquals(1, calls)
        } finally { active.cancel() }
    }

    @Test fun queuedImportDropsItsLockBeforeWaitingForFailedRecoveryToRetry() = runBlocking {
        val gate = SettingsImportRecoveryGate.readyForIsolatedStore()
        val mutex = Mutex(locked = true)
        var recovered = false
        var imported = false
        val queued = async(start = CoroutineStart.UNDISPATCHED) {
            gate.withReadyLock(mutex) { assertTrue(recovered); imported = true }
        }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            assertFalse(queued.isCompleted)
            gate.requireRecovery()
            mutex.unlock()
            withTimeout(5_000) { while (mutex.isLocked) yield() }
            assertFalse(imported)
            gate.start(scope) { mutex.withLock { recovered = true } }
            withTimeout(5_000) { queued.await() }
            assertTrue(imported)
        } finally { queued.cancelAndJoin(); scope.cancel() }
    }

    @Test fun retryResubscribesToTheRecoveredSnapshotInsteadOfReplayingPartialValues() = runBlocking {
        val gate = SettingsImportRecoveryGate.readyForIsolatedStore()
        val values = MutableStateFlow(7)
        val unsubscribed = CompletableDeferred<Unit>()
        val store = gate.wrap(object : DataStore<Int> {
            override val data: Flow<Int> = flow { try { emitAll(values) } finally { unsubscribed.complete(Unit) } }
            override suspend fun updateData(transform: suspend (Int) -> Int): Int = transform(values.value).also { values.value = it }
        })
        val original = CompletableDeferred<Unit>()
        val recovered = CompletableDeferred<Unit>()
        val actual = mutableListOf<Int>()
        val collection = launch {
            store.data.collect { value -> actual += value; if (value == 7) original.complete(Unit); if (value == 8) recovered.complete(Unit) }
        }
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            withTimeout(5_000) { original.await() }
            gate.requireRecovery()
            withTimeout(5_000) { unsubscribed.await() }
            values.value = 99 // Partial store state while the gate is closed.
            yield()
            assertEquals(listOf(7), actual)
            gate.start(scope) { values.value = 8 }
            withTimeout(5_000) { recovered.await() }
            assertEquals(listOf(7, 8), actual)
        } finally { collection.cancel(); scope.cancel() }
    }

    @Test fun firstReadAndWriteCannotReachTheStoreBeforeRecoveryCompletes() = runBlocking {
        val gate = SettingsImportRecoveryGate.pendingForTest()
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        var reads = 0
        var writes = 0
        val store = gate.wrap(object : DataStore<Int> {
            override val data: Flow<Int> = flow { reads++; emit(7) }
            override suspend fun updateData(transform: suspend (Int) -> Int): Int { writes++; return transform(7) }
        })
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            val read = async(start = CoroutineStart.UNDISPATCHED) { store.data.first() }
            val write = async(start = CoroutineStart.UNDISPATCHED) { store.updateData { it + 1 } }
            assertEquals(0, reads); assertEquals(0, writes)
            assertFalse(gate.isReady())
            gate.start(scope) { entered.complete(Unit); release.await() }
            withTimeout(5_000) { entered.await() }
            assertEquals(0, reads); assertEquals(0, writes)
            release.complete(Unit)
            assertEquals(7, withTimeout(5_000) { read.await() })
            assertEquals(8, withTimeout(5_000) { write.await() })
            assertEquals(1, reads); assertEquals(1, writes)
        } finally { scope.cancel() }
    }

    @Test fun failedRecoveryKeepsReadersSuspendedUntilExplicitRetrySucceeds() = runBlocking {
        val gate = SettingsImportRecoveryGate.pendingForTest()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        try {
            var attempts = 0
            gate.start(scope) { attempts++; if (attempts == 1) error("fixture recovery rejected") }
            withTimeout(5_000) { gate.state.first { it == SettingsImportRecoveryState.FAILED } }
            assertNull(withTimeoutOrNull(100) { gate.awaitReady() })
            assertFalse(gate.isReady())
            assertEquals(1, attempts)
            gate.retry()
            withTimeout(5_000) { gate.awaitReady() }
            assertEquals(2, attempts)
            assertTrue(gate.isReady())
        } finally { scope.cancel() }
    }
}
