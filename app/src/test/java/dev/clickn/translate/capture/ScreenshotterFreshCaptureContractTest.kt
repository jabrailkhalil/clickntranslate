package dev.clickn.translate.capture

import android.graphics.Bitmap
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ScreenshotterFreshCaptureContractTest {
    @Test
    fun onDemandBackendsDelegateFreshCaptureToTheExistingCaptureContract() = runBlocking {
        var requests = 0
        val onDemand = object : Screenshotter {
            override val isReady = true
            override suspend fun capture(): Bitmap? { requests++; return null }
            override fun release() = Unit
        }

        assertNull(onDemand.captureAfter(System.nanoTime()))
        assertEquals(1, requests)
        assertEquals(0L, onDemand.minimumLoopObservationIntervalMs)
    }
}
