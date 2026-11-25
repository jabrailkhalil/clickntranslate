package dev.clickn.translate.capture

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Real isolated SharedPreferences; no product choices, grants, Binder or settings are changed. */
@RunWith(AndroidJUnit4::class)
class CaptureStartPreferenceIntegrationTest {
    @Test fun explicitShizukuChoiceSurvivesStoreReopenAndPreservesOtherKeys() = runBlocking {
        withStorage { context, name, newStore ->
            withContext(Dispatchers.IO) {
                assertTrue(context.getSharedPreferences(name, Context.MODE_PRIVATE).edit()
                    .putString("unrelated", "retain me").commit())
            }
            val first = newStore()
            assertNull(first.store.mode.value)
            assertFalse(first.store.initialized.value)
            first.store.initialize(context, name)
            assertEquals(CaptureStartMode.SYSTEM, first.store.mode.value)
            first.store.select(CaptureStartMode.SHIZUKU)
            assertTrue(first.store.awaitPersistence())
            first.job.cancelAndJoin()

            val reopened = newStore()
            reopened.store.initialize(context, name)
            assertTrue(reopened.store.initialized.value)
            assertEquals(CaptureStartMode.SHIZUKU, reopened.store.mode.value)
            assertEquals("retain me", context.getSharedPreferences(name, Context.MODE_PRIVATE).getString("unrelated", null))
        }
    }

    @Test fun aSelectionMadeBeforeDiskInitializationWinsOverTheSavedChoice() = runBlocking {
        withStorage { context, name, newStore ->
            withContext(Dispatchers.IO) {
                assertTrue(context.getSharedPreferences(name, Context.MODE_PRIVATE).edit()
                    .putString("mode", CaptureStartMode.SHIZUKU.name).commit())
            }
            val first = newStore()
            first.store.select(CaptureStartMode.SYSTEM)
            first.store.initialize(context, name)
            assertEquals(CaptureStartMode.SYSTEM, first.store.mode.value)
            assertTrue(first.store.awaitPersistence())
            first.job.cancelAndJoin()
            val reopened = newStore()
            reopened.store.initialize(context, name)
            assertEquals(CaptureStartMode.SYSTEM, reopened.store.mode.value)
        }
    }

    @Test fun aRepeatedSystemChoiceRejectsALateShizukuAuthorizationWithoutAFlowValueChange() = runBlocking {
        withStorage { context, name, newStore ->
            val first = newStore()
            first.store.initialize(context, name)
            val authorizationRevision = first.store.revision()
            assertEquals(CaptureStartMode.SYSTEM, first.store.mode.value)
            first.store.select(CaptureStartMode.SYSTEM) // Same value, new explicit user intent.
            assertFalse(first.store.selectIfUnchanged(CaptureStartMode.SHIZUKU, authorizationRevision))
            assertEquals(CaptureStartMode.SYSTEM, first.store.mode.value)
            assertTrue(first.store.awaitPersistence())
            first.job.cancelAndJoin()
            val reopened = newStore()
            reopened.store.initialize(context, name)
            assertEquals(CaptureStartMode.SYSTEM, reopened.store.mode.value)
        }
    }

    @Test fun unsupportedStoredChoiceFallsBackToSystemWithoutOverwritingTheStoredValue() = runBlocking {
        withStorage { context, name, newStore ->
            withContext(Dispatchers.IO) {
                assertTrue(context.getSharedPreferences(name, Context.MODE_PRIVATE).edit()
                    .putString("mode", "unsupported_future_backend").commit())
            }
            val first = newStore()
            first.store.initialize(context, name)
            assertTrue(first.store.initialized.value)
            assertEquals(CaptureStartMode.SYSTEM, first.store.mode.value)
            assertEquals("unsupported_future_backend", context.getSharedPreferences(name, Context.MODE_PRIVATE).getString("mode", null))
        }
    }

    private class Handle(val store: CaptureStartPreferenceStore, val job: Job)

    private suspend fun withStorage(block: suspend (Context, String, () -> Handle) -> Unit) {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val name = "qa_capture_start_${UUID.randomUUID()}"
        val handles = mutableListOf<Handle>()
        try {
            block(context, name) {
                val job = SupervisorJob()
                Handle(CaptureStartPreferenceStore(CoroutineScope(job + Dispatchers.IO)), job).also(handles::add)
            }
        } finally {
            handles.forEach { it.job.cancelAndJoin() }
            withContext(Dispatchers.IO) { context.deleteSharedPreferences(name) }
        }
    }
}
