package dev.clickn.translate.service

import dev.clickn.translate.capture.CaptureGeometryBarrier
import dev.clickn.translate.capture.CaptureUiVisibility
import org.junit.Assert.*
import org.junit.Test

class OwnUiCaptureVisibilityTest {
    @Test fun aPreviousScreenBatchCannotReappearAfterEnteringAndLeavingTheMainUi() {
        val visibility = CaptureUiVisibility()
        val gate = TranslationBatchGate(visibility)
        gate.activate(1L)
        assertTrue(gate.accepts(1L))
        val main = Any()
        visibility.started(main)
        assertFalse(gate.accepts(1L))
        visibility.stopped(main)
        assertFalse("Leaving Main must not revive the previous screen result", gate.accepts(1L))
        gate.activate(2L)
        assertTrue("The next foreign-screen capture remains usable", gate.accepts(2L))
    }

    @Test fun aLateAdmissionWithAPreviousUiRevisionIsRejectedEvenAfterMainHasStopped() {
        val visibility = CaptureUiVisibility()
        val gate = TranslationBatchGate(visibility)
        val old = visibility.snapshot().revision
        val main = Any()
        visibility.started(main)
        gate.activate(1L)
        assertFalse("Do not admit capture while our window is visible", gate.accepts(1L))
        visibility.stopped(main)
        gate.activate(2L, old)
        assertFalse(gate.accepts(2L))
        gate.activate(3L, visibility.snapshot().revision)
        assertTrue(gate.accepts(3L))
    }

    @Test fun overlappingActivityOwnersKeepCaptureSuppressedUntilTheLastWindowStops() {
        val visibility = CaptureUiVisibility()
        val first = Any()
        val second = Any()
        visibility.started(first)
        val visibleRevision = visibility.snapshot().revision
        visibility.started(first) // Duplicate lifecycle signal is idempotent.
        visibility.started(second)
        visibility.stopped(first)
        visibility.stopped(Any()) // An unknown owner cannot release another window.
        assertTrue(visibility.snapshot().visible)
        assertEquals(visibleRevision, visibility.snapshot().revision)
        visibility.stopped(second)
        assertFalse(visibility.snapshot().visible)
        assertEquals(visibleRevision + 1L, visibility.snapshot().revision)
        visibility.stopped(second)
        assertEquals(visibleRevision + 1L, visibility.snapshot().revision)
    }

    @Test fun visibleNotificationClearsExistingPresentationBeforeTheLifecycleCallReturnsAndCanBeDetached() {
        val visibility = CaptureUiVisibility()
        var resultVisible = true
        var callbacks = 0
        val detach = visibility.observe {
            callbacks++
            if (visibility.snapshot().visible) resultVisible = false
        }
        assertEquals(1, callbacks)
        val main = Any()
        visibility.started(main)
        assertFalse(resultVisible)
        assertEquals(2, callbacks)
        detach()
        visibility.stopped(main)
        assertEquals("A destroyed service must not remain registered", 2, callbacks)
    }

    @Test fun returningToMainAlsoRetiresPreOcrWorkBeforeItCanBindItsUnchangedGeometry() {
        val visibility = CaptureUiVisibility()
        val geometry = CaptureGeometryBarrier()
        geometry.observeDisplay(1080, 2400)
        val before = geometry.snapshot()
        val detach = visibility.observe {
            if (visibility.snapshot().visible) geometry.retire()
        }
        try {
            val main = Any()
            visibility.started(main)
            visibility.stopped(main)
            assertFalse(geometry.bindBatch(1L, before))
            assertTrue(geometry.bindBatch(2L, geometry.snapshot()))
            assertTrue(geometry.acceptsBatch(2L))
            assertFalse("Visibility retirement keeps the valid display-size baseline",
                geometry.observeDisplay(1080, 2400))
        } finally { detach() }
    }
}
