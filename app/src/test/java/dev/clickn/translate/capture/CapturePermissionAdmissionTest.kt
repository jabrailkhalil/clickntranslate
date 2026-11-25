package dev.clickn.translate.capture

import org.junit.Assert.*
import org.junit.Test

/** Exercises the production admission protocol with external results and restored snapshots. */
class CapturePermissionAdmissionTest {
    @Test fun oneTapSurvivesBothExternalScreensWithoutDuplicateLaunchOrServiceAdmission() {
        var overlayLaunches = 0
        var projectionLaunches = 0
        var serviceStarts = 0
        val firstHost = CapturePermissionAdmission()
        if (firstHost.beginOverlay()) overlayLaunches++
        val returnedHost = CapturePermissionAdmission(firstHost.snapshot)
        if (returnedHost.beginOverlay()) overlayLaunches++
        assertEquals(1, overlayLaunches)
        assertTrue(returnedHost.consumeOverlayResult(granted = true))
        assertFalse("The same overlay callback cannot resume twice", returnedHost.consumeOverlayResult(true))
        if (returnedHost.beginProjection()) projectionLaunches++
        val rotatedHost = CapturePermissionAdmission(returnedHost.snapshot)
        if (rotatedHost.beginProjection()) projectionLaunches++
        assertEquals(1, projectionLaunches)
        if (rotatedHost.consumeProjectionResult()) serviceStarts++
        if (rotatedHost.consumeProjectionResult()) serviceStarts++
        assertEquals(1, serviceStarts)
        val finishedHost = CapturePermissionAdmission(rotatedHost.snapshot)
        assertFalse(finishedHost.beginOverlay())
        assertFalse(finishedHost.beginProjection())
        assertFalse(finishedHost.consumeProjectionResult())
    }

    @Test fun returningWithoutOverlayGrantFinishesAndShowsOnlyOneNotice() {
        val host = CapturePermissionAdmission()
        assertTrue(host.beginOverlay())
        assertTrue(host.consumeOverlayResult(granted = false))
        assertEquals(CapturePendingPermission.FINISHED, host.snapshot.pending)
        assertFalse(host.beginOverlay())
        assertFalse(host.beginProjection())
        val restored = CapturePermissionAdmission(host.snapshot)
        assertTrue(restored.consumeDeniedNotice())
        assertFalse(restored.consumeDeniedNotice())
        assertFalse(restored.consumeOverlayResult(true))
        assertFalse(restored.consumeProjectionResult())
    }

    @Test fun cancelledProjectionIsTerminalEvenAfterSuccessfulOverlayGrant() {
        val host = CapturePermissionAdmission()
        host.beginOverlay()
        host.consumeOverlayResult(true)
        assertTrue(host.beginProjection())
        // Both accepted and cancelled results consume the pending external result once.
        // Only the activity's genuine RESULT_OK+data branch calls coordinator.start.
        assertTrue(host.consumeProjectionResult())
        val restored = CapturePermissionAdmission(host.snapshot)
        assertEquals(CapturePendingPermission.FINISHED, restored.snapshot.pending)
        assertFalse(restored.beginProjection())
        assertFalse(restored.beginOverlay())
        assertFalse(restored.consumeProjectionResult())
        assertFalse(restored.consumeDeniedNotice())
    }

    @Test fun recreationDuringPreparationHasNoFictitiousLaunchedProjectionToken() {
        val beforeSettingsReturn = CapturePermissionAdmission()
        beforeSettingsReturn.beginOverlay()
        beforeSettingsReturn.consumeOverlayResult(true)
        // Preparation is cancellable; only immediately launching a real permission UI changes
        // pending from NONE. Recreating during the await must allow the new host to continue.
        assertEquals(CapturePendingPermission.NONE, beforeSettingsReturn.snapshot.pending)
        val recreated = CapturePermissionAdmission(beforeSettingsReturn.snapshot)
        assertTrue(recreated.beginProjection())
        assertFalse(recreated.beginProjection())
        assertEquals(CapturePendingPermission.PROJECTION, recreated.snapshot.pending)
    }

    @Test fun revokedGrantBetweenReturnAndPreparationCannotLoopBackIntoSettings() {
        val host = CapturePermissionAdmission()
        assertTrue(host.beginOverlay())
        assertTrue(host.consumeOverlayResult(true))
        assertTrue(host.snapshot.overlayAttempted)
        assertFalse("An attempted permission is not relaunched by a stale missing state", host.beginOverlay())
        host.finishOverlayDenied()
        val recreated = CapturePermissionAdmission(host.snapshot)
        assertTrue(recreated.consumeDeniedNotice())
        assertFalse(recreated.beginOverlay())
        assertFalse(recreated.beginProjection())
    }

    @Test fun lateResultsFromTheOtherPermissionScreenCannotConsumeCurrentAdmission() {
        val host = CapturePermissionAdmission()
        assertFalse(host.consumeOverlayResult(true))
        assertFalse(host.consumeProjectionResult())
        assertTrue(host.beginOverlay())
        val pending = host.snapshot
        assertFalse(host.consumeProjectionResult())
        assertEquals(pending, host.snapshot)
        host.consumeOverlayResult(true)
        assertTrue(host.beginProjection())
        val projection = host.snapshot
        assertFalse(host.consumeOverlayResult(false))
        assertEquals(projection, host.snapshot)
        host.finish()
        assertFalse(host.consumeProjectionResult())
    }
}
