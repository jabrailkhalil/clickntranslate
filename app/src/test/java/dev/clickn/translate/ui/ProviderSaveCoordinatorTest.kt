package dev.clickn.translate.ui

import java.io.IOException
import dev.clickn.translate.R
import dev.clickn.translate.data.SecureSettingsUnavailableException
import dev.clickn.translate.data.Settings
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
    @Test fun temporaryKeystoreFailureExplainsHowToRetryWithoutExposingCredentialDetails() = runTest {
        val saves = ProviderSaveCoordinator(backgroundScope)
        val failed = saves.save { throw SecureSettingsUnavailableException() }
        runCurrent()
        assertFalse(failed.await())
        assertEquals(R.string.settings_secure_storage_unavailable, saves.status.value.errorMessage)
        saves.clearFailure()
        assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
    }

    @Test fun delayedWriteCannotConfirmNavigationEarlyOrStartAnotherCommit() = runTest {
        val saves = ProviderSaveCoordinator(backgroundScope)
        val editor = ProviderEditSession(Settings())
        val disk = CompletableDeferred<Unit>()
        var provider = "ML_KIT"
        var writes = 0
        var confirmations = 0
        editor.submit(openAdvanced = true) {
            saves.save {
                writes++
                disk.await()
                provider = "OPENAI"
            }
        }
        val request = requireNotNull(editor.pending.value)
        assertEquals(ProviderSaveStatus.SAVING, saves.status.value)
        assertSame(request.commit, saves.save { fail("A second write started before the first finished") })
        editor.submit(openAdvanced = false) { error("A second tap replaced the pending action") }
        val ui = launch {
            editor.finish(request) { advanced ->
                assertTrue(advanced)
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
        val editor = ProviderEditSession(Settings())
        var confirmations = 0
        editor.submit(false) { saves.save { throw IOException("Storage unavailable") } }
        val failed = requireNotNull(editor.pending.value)
        runCurrent()
        editor.finish(failed) { confirmations++ }
        assertNull(editor.pending.value)
        assertEquals(ProviderSaveStatus.FAILED, saves.status.value)
        assertEquals(0, confirmations)
        var persisted = false
        editor.submit(false) { saves.save { persisted = true } }
        val retried = requireNotNull(editor.pending.value)
        assertEquals(ProviderSaveStatus.SAVING, saves.status.value)
        runCurrent()
        editor.finish(retried) { advanced ->
            assertFalse(advanced)
            assertTrue(persisted)
            confirmations++
        }
        assertEquals(1, confirmations)
        assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
    }

    @Test fun cancellingTheUiWaitLeavesTheViewModelCommitAliveWithoutLateNavigation() = runTest {
        val saves = ProviderSaveCoordinator(backgroundScope)
        val editor = ProviderEditSession(Settings())
        val disk = CompletableDeferred<Unit>()
        var persisted = false
        var confirmations = 0
        editor.submit(true) { saves.save { disk.await(); persisted = true } }
        val request = requireNotNull(editor.pending.value)
        val ui = launch { editor.finish(request) { confirmations++ } }
        runCurrent()
        ui.cancelAndJoin()
        assertTrue(request.commit.isActive)
        assertEquals(ProviderSaveStatus.SAVING, saves.status.value)
        disk.complete(Unit)
        runCurrent()
        assertTrue(request.commit.await())
        assertTrue(persisted)
        assertEquals(0, confirmations)
        assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
        val afterRotation = requireNotNull(editor.pending.value)
        editor.finish(afterRotation) { advanced -> assertTrue(advanced); confirmations++ }
        editor.finish(afterRotation) { fail("Already consumed navigation") }
        assertEquals(1, confirmations)
        assertNull(editor.pending.value)
    }

    @Test fun ownerCancellationCannotConfirmOrLeaveSavingStuckBeforeTheWriteStarts() = runTest {
        val lifetime = SupervisorJob()
        val owner = CoroutineScope(backgroundScope.coroutineContext + lifetime)
        val saves = ProviderSaveCoordinator(owner)
        val editor = ProviderEditSession(Settings())
        lifetime.cancel()
        var writes = 0
        editor.submit(false) { saves.save { writes++ } }
        runCurrent()
        try {
            editor.finish(requireNotNull(editor.pending.value)) { fail("A destroyed owner confirmed a save") }
            fail("Cancelled persistence was treated as success")
        } catch (_: CancellationException) {
            assertEquals(0, writes)
            assertEquals(ProviderSaveStatus.IDLE, saves.status.value)
        }
    }
}
