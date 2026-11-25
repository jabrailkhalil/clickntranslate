// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import dev.clickn.translate.capture.ShizukuCaptureRoute
import dev.clickn.translate.capture.resolveShizukuCaptureRoute
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SettledPageLoopWiringTest {

    @Test
    fun settledPageMode_isWiredFromSettingsToIndependentObservationAndInvalidation() {
        data class Marker(val name: String, val source: String, val expected: String)

        val cases = listOf(
            Marker("persisted enum", source("data/Settings.kt"), "SETTLED_PAGE"),
            Marker("settings chip", source("ui/SettingsScreen.kt"), "LoopTriggerMode.SETTLED_PAGE"),
            Marker("independent observer", source("service/CaptureService.kt"), "observeSettledPage()"),
            Marker("latest page policy", source("service/CaptureService.kt"), "settledPagePolicy.observe("),
            Marker("old work invalidation", source("service/CaptureService.kt"), "invalidateSettledPageWork("),
            Marker("old translation cancellation", source("service/CaptureService.kt"), "cancelActiveTranslationBatch(\"settledPage:${'$'}reason\")"),
            Marker("clean observation", source("service/CaptureService.kt"), "captureCleanSourceFrame("),
            Marker("late OCR rejection", source("service/CaptureService.kt"), "ensureCurrentSettledPage(settledPageRevision"),
            Marker("read-only overlay bounds", source("overlay/OverlayManager.kt"), "observationExclusionRects()"),
        )

        cases.forEach { case ->
            assertTrue(case.name, case.source.contains(case.expected))
        }
        val observer = source("service/CaptureService.kt").substringAfter("private suspend fun observeSettledPage()")
            .substringBefore("private fun selectLoopTextRoi(")
        assertTrue("observation uses reversible source capture", observer.contains("captureCleanSourceFrame("))
        assertFalse("visual observations must not run OCR directly", observer.contains("ocrEngine.recognize("))
    }

    @Test
    fun ShizukuObservation_isPacedAndRawCaptureAvoidsTheGrowingBufferPath() {
        val screenshotter = source("capture/ShizukuScreenshotter.kt")
        val rawPath = screenshotter.substringAfter("private fun executeRawScreencap()")
            .substringBefore("private fun executeScreencap(")

        assertTrue(screenshotter.contains("minimumLoopObservationIntervalMs"))
        assertTrue(screenshotter.contains("MIN_LOOP_OBSERVATION_INTERVAL_MS = 350L"))
        assertTrue(screenshotter.contains("accessibilityFastPath.capture()"))
        assertTrue(rawPath.contains("ByteArray(currentFrameBytes)"))
        assertFalse(rawPath.contains("ByteArrayOutputStream"))
        assertFalse(rawPath.contains("toByteArray()"))
    }

    @Test
    fun ShizukuCaptureRoute_prefersDirectAccessibilityAndFallsBackToShell() {
        data class Case(
            val accessibilityReady: Boolean,
            val shizukuReady: Boolean,
            val expected: ShizukuCaptureRoute,
        )

        listOf(
            Case(accessibilityReady = true, shizukuReady = true, expected = ShizukuCaptureRoute.ACCESSIBILITY),
            Case(accessibilityReady = true, shizukuReady = false, expected = ShizukuCaptureRoute.ACCESSIBILITY),
            Case(accessibilityReady = false, shizukuReady = true, expected = ShizukuCaptureRoute.SHELL),
            Case(accessibilityReady = false, shizukuReady = false, expected = ShizukuCaptureRoute.UNAVAILABLE),
        ).forEach { case ->
            assertEquals(
                case.toString(),
                case.expected,
                resolveShizukuCaptureRoute(case.accessibilityReady, case.shizukuReady),
            )
        }
    }

    private fun source(relative: String): String =
        File("src/main/java/dev/clickn/translate/$relative").readText()

}
