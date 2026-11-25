package dev.clickn.translate.ui

import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.capture.CaptureGeometryBarrier
import dev.clickn.translate.capture.MainCaptureUiVisibility
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

/** Fullscreen lifecycle ownership; this does not model every STARTED multiwindow arrangement. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class)
@LooperMode(LooperMode.Mode.PAUSED)
class OwnUiActivityLifecycleRuntimeTest {
    @Test fun backgroundStartAndStopWithoutResumeDoNotRetireForegroundCapture() {
        val visibility = MainCaptureUiVisibility
        val initial = visibility.snapshot()
        assertFalse("No earlier Main Activity may remain owned", initial.visible)
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(1080, 2400)
        val generation = geometry.snapshot()
        assertTrue(geometry.bindBatch(1L, generation))
        var retireCalls = 0
        val observed = mutableListOf<Boolean>()
        val detach = visibility.observe {
            observed += visibility.snapshot().visible
            if (visibility.snapshot().visible) {
                retireCalls++
                geometry.retire()
            }
        }
        val controller = Robolectric.buildActivity(MainActivity::class.java).create()
        var destroyed = false
        try {
            assertEquals(initial, visibility.snapshot())
            controller.start()
            assertEquals("START without RESUME must not claim the foreground", initial, visibility.snapshot())
            assertEquals(listOf(false), observed)
            assertEquals(0, retireCalls)
            assertTrue(geometry.acceptsBatch(1L))

            controller.stop()
            assertEquals(initial, visibility.snapshot())
            controller.destroy()
            destroyed = true
            assertEquals("An unknown owner cannot advance the revision on teardown", initial, visibility.snapshot())
            assertEquals(listOf(false), observed)
            assertEquals(0, retireCalls)
            assertEquals(generation, geometry.snapshot())
            assertTrue(geometry.acceptsBatch(1L))
            assertTrue(visibility.allowsPresentation(initial.revision))
        } finally {
            try {
                if (!destroyed) controller.destroy()
            } finally {
                detach()
            }
        }
    }

    @Test fun resumeClaimsSynchronouslyPauseKeepsOwnershipAndStopThenDestroyReleaseOnce() {
        val visibility = MainCaptureUiVisibility
        val initial = visibility.snapshot()
        assertFalse("No earlier Main Activity may remain owned", initial.visible)
        val observed = mutableListOf<Boolean>()
        var retireCalls = 0
        val detach = visibility.observe {
            observed += visibility.snapshot().visible
            if (visibility.snapshot().visible) retireCalls++
        }
        val controller = Robolectric.buildActivity(MainActivity::class.java).create()
        var destroyed = false
        try {
            controller.start()
            assertEquals(initial, visibility.snapshot())
            controller.resume()
            // No looper idle or draw is required for the capture observer to see this barrier.
            val resumed = visibility.snapshot()
            assertTrue(resumed.visible)
            assertEquals(initial.revision + 1L, resumed.revision)
            assertEquals(listOf(false, true), observed)
            assertEquals(1, retireCalls)
            assertFalse(visibility.allowsPresentation(initial.revision))

            controller.pause()
            assertEquals("A paused but not stopped Main must remain protected", resumed, visibility.snapshot())
            assertEquals(listOf(false, true), observed)
            assertEquals(1, retireCalls)

            controller.stop()
            val stopped = visibility.snapshot()
            assertFalse(stopped.visible)
            assertEquals(resumed.revision + 1L, stopped.revision)
            assertEquals(listOf(false, true, false), observed)
            assertEquals(1, retireCalls)
            assertFalse("Leaving Main must not revive an earlier capture", visibility.allowsPresentation(initial.revision))
            assertTrue(visibility.allowsPresentation(stopped.revision))

            controller.destroy()
            destroyed = true
            assertEquals("Destroy after Stop must be an idempotent release", stopped, visibility.snapshot())
            assertEquals(listOf(false, true, false), observed)
            assertEquals(1, retireCalls)
        } finally {
            try {
                if (!destroyed) controller.destroy()
            } finally {
                detach()
            }
        }
    }
}
