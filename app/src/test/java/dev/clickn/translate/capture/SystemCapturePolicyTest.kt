// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import dev.clickn.translate.shizuku.ShizukuCapabilities
import java.io.File
import org.junit.Assert.*
import org.junit.Test

class SystemCapturePolicyTest {
    @Test fun startControlsDoNotRequireASeparateOverlayGrantWhenShizukuIsReady() {
        val availabilityCases = listOf(
            ShizukuCapabilities.Availability.READY to true,
            ShizukuCapabilities.Availability.INSTALLED_NOT_GRANTED to false,
            ShizukuCapabilities.Availability.INSTALLED_NOT_PAIRED to false,
            ShizukuCapabilities.Availability.INSTALLED_COMPATIBILITY_REQUIRED to false,
            ShizukuCapabilities.Availability.NOT_INSTALLED to false,
            ShizukuCapabilities.Availability.NOT_RUNNING to false,
        )
        assertEquals(ShizukuCapabilities.Availability.entries.toSet(), availabilityCases.map { it.first }.toSet())
        for ((availability, readyWithoutOverlay) in availabilityCases) {
            for (granted in listOf(false, true)) for (running in listOf(false, true)) {
                val expected = when {
                    running -> true // Never hide Stop if the permission is revoked while running.
                    granted -> true
                    else -> readyWithoutOverlay
                }
                assertEquals("$availability granted=$granted running=$running", expected,
                    showCaptureStartControls(granted, running, availability))
            }
        }
    }

    @Test fun startingCaptureDoesNotSilentlyEnableAccessibilityOrConfigureOtherPermissions() {
        val coordinator = File("src/main/java/dev/clickn/translate/capture/CaptureStartCoordinator.kt").readText()
        assertFalse(coordinator.contains("permissions.configure("))
        assertFalse(coordinator.contains("permissions.configureIfReady("))
        assertFalse(coordinator.contains("grantOverlayPermission("))
        assertTrue(coordinator.contains("CaptureStartPreference.initialize(context)"))
        assertTrue(coordinator.contains("if (!Settings.canDrawOverlays(context)) return CaptureStartDecision.OpenOverlaySettings"))
    }

    @Test fun systemBackendTable() {
        for (sdk in listOf(26, 29, 30, 33, 34, 35, 36)) {
            for (connected in listOf(false, true)) for (capable in listOf(false, true)) {
                val expected = if (sdk >= 30 && connected && capable) CaptureBackend.ACCESSIBILITY
                    else CaptureBackend.MEDIA_PROJECTION
                assertEquals("sdk=$sdk connected=$connected capable=$capable", expected,
                    systemCaptureBackend(sdk, connected, capable))
            }
        }
    }

    @Test fun explicitChoiceWinsAndANewInstallationNeverImplicitlySelectsShizuku() {
        for (state in ShizukuCapabilities.Availability.entries) {
            for (choice in CaptureStartMode.entries) {
                assertEquals(choice, resolveCaptureStartMode(choice, state))
            }
            assertEquals(CaptureStartMode.SYSTEM, resolveCaptureStartMode(null, state))
        }
    }

    @Test fun startGateRejectsDuplicateAndReleasesForRetry() {
        val gate = CaptureStartGate()
        repeat(5) {
            assertTrue(gate.acquire())
            repeat(10) { assertFalse(gate.acquire()) }
            gate.release()
        }
    }

    @Test fun pacingIncludesCancelledOrFailedRequestsAndHandlesClockReset() {
        val pacing = AccessibilityScreenshotPacing()
        assertEquals(0L, pacing.delayBeforeRequest(1_000))
        pacing.requestStarted(1_000)
        listOf(1_000L to 350L, 1_100L to 250L, 1_333L to 17L,
            1_350L to 0L, 2_000L to 0L, 900L to 0L).forEach { (now, wait) ->
            assertEquals("now=$now", wait, pacing.delayBeforeRequest(now))
        }
        pacing.requestStarted(1_350)
        assertEquals(350L, pacing.delayBeforeRequest(1_350))
    }

    @Test fun startupAndScreenshotWiringPreservesSharedPipelineAndConsentLifecycle() {
        fun source(path: String) = File("src/main/$path").readText()
        val activity = source("java/dev/clickn/translate/capture/CaptureStartRequestActivity.kt")
        val coordinator = source("java/dev/clickn/translate/capture/CaptureStartCoordinator.kt")
        val screenshot = source("java/dev/clickn/translate/capture/AccessibilityScreenshotter.kt")
        val capture = source("java/dev/clickn/translate/service/CaptureService.kt")
        val manifest = source("AndroidManifest.xml")
        val entry = manifest.substringAfter("android:name=\".capture.CaptureStartRequestActivity\"")
            .substringBefore("/>")
        assertFalse("must survive the system permission activity", entry.contains("noHistory"))
        assertTrue(activity.contains("coordinator.gate.acquire()"))
        assertTrue(activity.contains("if (ownsGate) coordinator.gate.release()"))
        assertTrue(activity.contains("savedState[\"projectionRequested\"] = true"))
        assertTrue(activity.contains("Activity.RESULT_OK"))
        assertTrue(activity.contains("coordinator.start(CaptureBackend.MEDIA_PROJECTION"))
        assertTrue(coordinator.indexOf("verifyShellPrivilegeAsync()") < coordinator.indexOf("resolveCaptureStartMode("))
        assertTrue(coordinator.contains("CaptureServiceState.running.value"))
        assertTrue(coordinator.contains("if (!Settings.canDrawOverlays(context)) return CaptureStartDecision.OpenOverlaySettings"))
        assertTrue(coordinator.indexOf("if (useShizuku && !shizuku.ensureReady())") <
            coordinator.indexOf("return CaptureStartDecision.Ready(CaptureBackend.SHIZUKU)"))
        assertTrue(capture.contains("screenshotter = AccessibilityScreenshotter()"))
        for (marker in listOf("requestMutex.withLock", "withTimeoutOrNull", "buffer.close()",
            "hardwareBitmap?.recycle()", "onCancellation", "Bitmap.Config.ARGB_8888", "released.get()")) {
            assertTrue(marker, screenshot.contains(marker))
        }
        for (forbidden in listOf("createBitmap(", "saveBitmap", "createScreenCaptureIntent", "captureRegion")) {
            assertFalse(forbidden, screenshot.contains(forbidden))
        }
        assertTrue(source("res/xml-v30/a11y_config.xml").contains("android:canTakeScreenshot=\"true\""))
        assertFalse(source("res/xml/a11y_config.xml").contains("canTakeScreenshot"))
        // No new error copy or separate third screenshot control was introduced.
        val zh = source("res/values-zh-rCN/strings.xml")
        assertTrue(zh.contains("根据设备和授权状态选择截屏方式，必要时需要确认授权。"))
        assertTrue(zh.contains("<string name=\"main_capture_system\">系统截屏</string>"))
    }

    @Test fun everyEntryUsesTheSingleStartupCoordinator() {
        val sources = File("src/main/java/dev/clickn/translate").walkTopDown()
            .filter { it.isFile && it.extension == "kt" }.toList()
        assertEquals(listOf("CaptureStartCoordinator.kt"), sources.filter {
            it.readText().contains("CaptureService.ACTION_START")
        }.map { it.name })
        assertEquals(listOf("CaptureStartRequestActivity.kt"), sources.filter {
            it.readText().contains("createScreenCaptureIntent()")
        }.map { it.name })
    }
}
