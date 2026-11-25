package dev.clickn.translate.service

import android.app.Application
import android.graphics.Bitmap
import dev.clickn.translate.overlay.SourceObservationLease
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

/** Executes the coroutine/bitmap ownership contract; no source-text assertions. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class)
@LooperMode(LooperMode.Mode.PAUSED)
class SourceObservationCaptureRuntimeTest {
    private val uiThread = AtomicReference<Thread>()

    @Test fun changedWindowsSettleBeforeCaptureAndRestoreInReverseOrderOnUi() = withUi { ui ->
        val events = mutableListOf<String>()
        val image = bitmap()
        val helper = SourceObservationCapture(ui, settle = {
            assertUiThread()
            events += "settle"
        }, nanoTime = {
            assertUiThread()
            events += "fence"
            417L
        })
        val first = lease("first", true, events)
        val second = lease("second", false, events)
        try {
            val result = helper.capture(isValid = {
                assertUiThread()
                true
            }, acquire = {
                assertUiThread()
                events += "hide:first"
                add(first)
                events += "hide:second"
                add(second)
            }, capture = { fence ->
                assertEquals(417L, fence)
                assertNotSame(requireNotNull(uiThread.get()), Thread.currentThread())
                events += "capture"
                image
            })
            assertSame(image, result)
            assertFalse(image.isRecycled)
            assertEquals(listOf("fence", "hide:first", "hide:second", "settle", "capture",
                "close:second", "close:first"), events)
            assertEquals(1, first.closeCalls)
            assertEquals(1, second.closeCalls)
        } finally {
            image.recycle()
        }
    }

    @Test fun alreadyHiddenWindowsDoNotWaitOrRequireANewFrame() = withUi { ui ->
        var captureCalls = 0
        val helper = SourceObservationCapture(ui, settle = { error("No UI changed") }, nanoTime = { 91L })
        val hidden = lease("hidden", false)
        assertNull(helper.capture({ true }, { add(hidden) }, { fence ->
            captureCalls++
            assertNull(fence)
            null
        }))
        assertEquals(1, captureCalls)
        assertEquals(1, hidden.closeCalls)
    }

    @Test fun invalidBeforeAcquisitionDoesNotTouchWindowsOrCapture() = withUi { ui ->
        val helper = SourceObservationCapture(ui, settle = { error("No settle") }, nanoTime = { error("No fence") })
        assertNull(helper.capture(isValid = {
            assertUiThread()
            false
        }, acquire = { error("No acquire") }, capture = { error("No capture") }))
    }

    @Test fun partialAcquisitionFailureStillClosesEveryRegisteredLease() = withUi { ui ->
        val events = mutableListOf<String>()
        val first = lease("first", true, events)
        val second = lease("second", true, events)
        val expected = FixtureFailure("Window unavailable")
        val helper = SourceObservationCapture(ui, settle = { error("No settle") })
        val failure = caught {
            helper.capture({ true }, {
                add(first)
                add(second)
                throw expected
            }, { error("No capture") })
        }
        assertSame(expected, failure)
        assertEquals(listOf("close:second", "close:first"), events)
        assertEquals(1, first.closeCalls)
        assertEquals(1, second.closeCalls)
    }

    @Test fun cancellationWhileSettlingRestoresLeasesWithoutCapturing() = withUi { ui ->
        val settling = CompletableDeferred<Unit>()
        val hidden = lease("window", true)
        var captureCalls = 0
        val helper = SourceObservationCapture(ui, settle = {
            settling.complete(Unit)
            awaitCancellation()
        })
        val operation = launch {
            helper.capture({ true }, { add(hidden) }, { captureCalls++; null })
        }
        withTimeout(2_000) { settling.await() }
        operation.cancelAndJoin()
        assertEquals(0, captureCalls)
        assertEquals(1, hidden.closeCalls)
    }

    @Test fun cancellationWhileCapturingRestoresLeases() = withUi { ui ->
        val capturing = CompletableDeferred<Unit>()
        val hidden = lease("window", true)
        val helper = SourceObservationCapture(ui, settle = {})
        val operation = launch {
            helper.capture({ true }, { add(hidden) }, {
                capturing.complete(Unit)
                awaitCancellation()
            })
        }
        withTimeout(2_000) { capturing.await() }
        operation.cancelAndJoin()
        assertEquals(1, hidden.closeCalls)
    }

    @Test fun cancellationJustBeforeBitmapReturnsDoesNotLoseBitmapOwnership() = withUi { ui ->
        val image = bitmap()
        val hidden = lease("window", true)
        val helper = SourceObservationCapture(ui, settle = {})
        try {
            val operation = launch {
                helper.capture({ true }, { add(hidden) }, {
                    currentCoroutineContext().cancel()
                    image
                })
            }
            operation.join()
            assertTrue(operation.isCancelled)
            assertTrue(image.isRecycled)
            assertEquals(1, hidden.closeCalls)
        } finally {
            if (!image.isRecycled) image.recycle()
        }
    }

    @Test fun invalidatedWhileSettlingDoesNotStartCapture() = withUi { ui ->
        var valid = true
        val hidden = lease("window", true)
        val helper = SourceObservationCapture(ui, settle = { valid = false })
        assertNull(helper.capture({ valid }, { add(hidden) }, { error("Stale operation captured") }))
        assertEquals(1, hidden.closeCalls)
    }

    @Test fun invalidatedAfterCaptureRecyclesResultAndDoesNotResurrectRemovedWindow() = withUi { ui ->
        var valid = true
        val window = VersionedWindow()
        val image = bitmap()
        val helper = SourceObservationCapture(ui, settle = {})
        try {
            val result = helper.capture({ valid }, { add(window.hide()) }, {
                valid = false
                window.remove()
                image
            })
            assertNull(result)
            assertTrue(image.isRecycled)
            assertFalse(window.visible)
            assertEquals(0, window.leases)
        } finally {
            if (!image.isRecycled) image.recycle()
        }
    }

    @Test fun callerOwnedOuterLeaseRemainsHiddenUntilCallerClosesIt() = withUi { ui ->
        val window = VersionedWindow()
        val outer = window.hide()
        val helper = SourceObservationCapture(ui, settle = { error("Outer lease already hid the window") })
        try {
            assertNull(helper.capture({ true }, { add(window.hide()) }, { fence ->
                assertNull(fence)
                assertFalse(window.visible)
                assertEquals(2, window.leases)
                null
            }))
            assertFalse(window.visible)
            assertEquals(1, window.leases)
        } finally {
            outer.close()
        }
        assertTrue(window.visible)
        assertEquals(0, window.leases)
    }

    @Test fun captureFailurePreservesOriginalErrorAndStillClosesOtherLeases() = withUi { ui ->
        val expected = FixtureFailure("Capture failed")
        val closeFailure = FixtureFailure("Window close failed")
        val events = mutableListOf<String>()
        val first = lease("first", true, events)
        val second = lease("second", true, events) { throw closeFailure }
        val helper = SourceObservationCapture(ui, settle = {})
        val failure = caught {
            helper.capture({ true }, { add(first); add(second) }, { throw expected })
        }
        assertSame(expected, failure)
        assertEquals(listOf(closeFailure), failure.suppressed.toList())
        assertEquals(listOf("close:second", "close:first"), events)
        assertEquals(1, first.closeCalls)
    }

    @Test fun restorationFailureRecyclesOtherwiseSuccessfulBitmap() = withUi { ui ->
        val image = bitmap()
        val expected = FixtureFailure("Window close failed")
        val first = lease("first", true)
        val second = lease("second", true) { throw expected }
        val helper = SourceObservationCapture(ui, settle = {})
        try {
            val failure = caught {
                helper.capture({ true }, { add(first); add(second) }, { image })
            }
            assertSame(expected, failure)
            assertTrue(image.isRecycled)
            assertEquals(1, first.closeCalls)
            assertEquals(1, second.closeCalls)
        } finally {
            if (!image.isRecycled) image.recycle()
        }
    }

    @Test fun cancellationDuringRestorationCannotSkipRemainingLeasesOrDeliverBitmap() = withUi { ui ->
        val image = bitmap()
        val first = lease("first", true)
        lateinit var operation: Job
        val second = lease("second", true) { operation.cancel() }
        val helper = SourceObservationCapture(ui, settle = {})
        try {
            operation = launch {
                helper.capture({ true }, { add(first); add(second) }, { image })
            }
            operation.join()
            assertTrue(operation.isCancelled)
            assertTrue(image.isRecycled)
            assertEquals(1, first.closeCalls)
            assertEquals(1, second.closeCalls)
        } finally {
            if (!image.isRecycled) image.recycle()
        }
    }

    private fun bitmap() = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888)

    private fun lease(
        name: String,
        changed: Boolean,
        events: MutableList<String> = mutableListOf(),
        onClose: () -> Unit = {},
    ) = TestLease(changed) {
        assertUiThread()
        events += "close:$name"
        onClose()
    }

    private class TestLease(override val changedVisibility: Boolean, private val onClose: () -> Unit) : SourceObservationLease {
        var closeCalls = 0
        override fun close() {
            closeCalls++
            onClose()
        }
    }

    /**
     * Extra fixture state prevents coroutine stacktrace recovery from copying this exception.
     * Identity assertions then verify exact error/suppressed ownership across dispatchers.
     */
    private class FixtureFailure(message: String) : IllegalStateException(message) {
        val ownerToken = Any()
    }

    /** Models the manager contract: releasing a lease cannot recreate a removed window. */
    private class VersionedWindow {
        var visible = true
            private set
        var leases = 0
            private set
        private var version = 0

        fun hide(): SourceObservationLease {
            val expectedVersion = version
            val changed = visible
            visible = false
            leases++
            return TestLease(changed) {
                leases--
                if (changed && version == expectedVersion && leases == 0) visible = true
            }
        }

        fun remove() {
            version++
            visible = false
        }
    }

    private suspend fun caught(block: suspend () -> Unit): Throwable {
        try {
            block()
        } catch (error: Throwable) {
            return error
        }
        error("Expected failure")
    }

    private fun withUi(block: suspend CoroutineScope.(CoroutineDispatcher) -> Unit) {
        val ui = Executors.newSingleThreadExecutor { task ->
            Thread(task, UI_THREAD).also(uiThread::set)
        }.asCoroutineDispatcher()
        try {
            runBlocking { withTimeout(5_000) { block(ui) } }
        } finally {
            ui.close()
        }
    }

    private fun assertUiThread() = assertSame(requireNotNull(uiThread.get()), Thread.currentThread())

    private companion object {
        const val UI_THREAD = "source-observation-ui"
    }
}
