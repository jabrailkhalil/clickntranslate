package dev.clickn.translate.ui

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

class ProviderSaveCoordinatorTest {
    @Test fun delayedWriteCannotConfirmNavigationEarlyOrStartAnotherCommit() = runTest {
        val saves = ProviderSaveCoordinator(backgroundScope)
        val disk = CompletableDeferred<Unit>()
        var provider = "ML_KIT"
        var writes = 0
        var confirmations = 0
        val commit = saves.save {
            writes++
            disk.await()
            provider = "OPENAI"
        }
        assertEquals(ProviderSaveStatus.SAVING, saves.status.value)
        assertSame(commit, saves.save { fail("A second write started before the first finished") })
        val ui = launch {
            confirmProviderSave(commit) {
                assertEquals("OPENAI", provider)
                confirmations++
            }
        }
        runCurrent()
        assertEquals("ML_KIT", provider)
        assertEquals(0, confirmations)
        assertEquals(1, writes)
        disk.complete(Unit)
        runCurrent()
        ui.join()
        assertEquals(1, confirmations)
        assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
    }

    @Test fun persistenceFailureStaysInTheSheetAndCanBeRetriedSuccessfully() = runTest {
        val saves = ProviderSaveCoordinator(backgroundScope)
        var confirmations = 0
        val failed = saves.save { throw IOException("Storage unavailable") }
        runCurrent()
        assertFalse(confirmProviderSave(failed) { confirmations++ })
        assertEquals(ProviderSaveStatus.FAILED, saves.status.value)
        assertEquals(0, confirmations)
        var persisted = false
        val retried = saves.save { persisted = true }
        assertEquals(ProviderSaveStatus.SAVING, saves.status.value)
        runCurrent()
        assertTrue(confirmProviderSave(retried) {
            assertTrue(persisted)
            confirmations++
        })
        assertEquals(1, confirmations)
        assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
    }

    @Test fun cancellingTheUiWaitLeavesTheViewModelCommitAliveWithoutLateNavigation() = runTest {
        val saves = ProviderSaveCoordinator(backgroundScope)
        val disk = CompletableDeferred<Unit>()
        var persisted = false
        var confirmations = 0
        val commit = saves.save { disk.await(); persisted = true }
        val ui = launch { confirmProviderSave(commit) { confirmations++ } }
        runCurrent()
        ui.cancelAndJoin()
        assertTrue(commit.isActive)
        assertEquals(ProviderSaveStatus.SAVING, saves.status.value)
        disk.complete(Unit)
        runCurrent()
        assertTrue(commit.await())
        assertTrue(persisted)
        assertEquals(0, confirmations)
        assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
    }

    @Test fun ownerCancellationCannotConfirmOrLeaveSavingStuckBeforeTheWriteStarts() = runTest {
        val lifetime = SupervisorJob()
        val owner = CoroutineScope(backgroundScope.coroutineContext + lifetime)
        val saves = ProviderSaveCoordinator(owner)
        lifetime.cancel()
        var writes = 0
        val commit = saves.save { writes++ }
        runCurrent()
        try {
            confirmProviderSave(commit) { fail("A destroyed owner confirmed a save") }
            fail("Cancelled persistence was treated as success")
        } catch (_: CancellationException) {
            assertEquals(0, writes)
            assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
        }
    }
}
