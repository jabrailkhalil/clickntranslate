package dev.clickn.translate.capture

import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.PixelFormat
import androidx.test.ext.junit.runners.AndroidJUnit4
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Controlled processes and real Android Bitmap decoding; no device permissions or Shizuku service. */
@RunWith(AndroidJUnit4::class)
class ShizukuScreenshotterIntegrationTest {
    @Test fun currentAndLegacyRawHeadersDecodeWithoutPngFallback() = runBlocking {
        for (headerBytes in listOf(12, 16)) {
            val frame = ByteBuffer.allocate(headerBytes + 8).order(ByteOrder.LITTLE_ENDIAN).apply {
                putInt(1); putInt(2); putInt(PixelFormat.RGBA_8888)
                if (headerBytes == 16) putInt(0)
                put(byteArrayOf(0x12, 0x12, 0x12, -1, 0x77, 0x77, 0x77, -1))
            }.array()
            val process = CompletedProcess(frame)
            val requests = mutableListOf<String>()
            val screenshotter = shellScreenshotter { command ->
                requests += command.joinToString(" ")
                process
            }
            try {
                val bitmap = withTimeout(2_000) { screenshotter.capture() }
                assertNotNull(bitmap)
                try {
                    assertEquals(1, bitmap!!.width)
                    assertEquals(2, bitmap.height)
                    assertEquals(Color.rgb(0x12, 0x12, 0x12), bitmap.getPixel(0, 0))
                    assertEquals(Color.rgb(0x77, 0x77, 0x77), bitmap.getPixel(0, 1))
                } finally { bitmap?.recycle() }
                assertEquals(listOf("screencap"), requests)
                assertEquals(1, process.destroys.get())
            } finally { screenshotter.release() }
        }
    }

    @Test fun invalidRawFrameFallsBackToBoundedPngAndReturnsDecodedPixels() = runBlocking {
        val image = Bitmap.createBitmap(2, 1, Bitmap.Config.ARGB_8888).apply { eraseColor(Color.MAGENTA) }
        val png = try {
            ByteArrayOutputStream().also { assertTrue(image.compress(Bitmap.CompressFormat.PNG, 100, it)) }.toByteArray()
        } finally { image.recycle() }
        val requests = mutableListOf<String>()
        val processes = mutableListOf<CompletedProcess>()
        val screenshotter = shellScreenshotter { command ->
            requests += command.joinToString(" ")
            CompletedProcess(if (requests.size == 1) byteArrayOf(0) else png).also(processes::add)
        }
        try {
            val bitmap = withTimeout(2_000) { screenshotter.capture() }
            assertNotNull(bitmap)
            try { assertEquals(Color.MAGENTA, bitmap!!.getPixel(1, 0)) } finally { bitmap?.recycle() }
            assertEquals(listOf("screencap", "screencap -p"), requests)
            assertTrue(processes.all { it.destroys.get() == 1 })
        } finally { screenshotter.release() }
    }

    @Test fun accessibilityBitmapArrivingAfterReleaseIsRecycledAndNeverReturned() = runBlocking {
        val bitmap = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888)
        val source = DeferredAccessibility(bitmap)
        val screenshotter = ShizukuScreenshotter(source, { false }, { error("No shell fallback after release") })
        val capture = async { screenshotter.capture() }
        try {
            withTimeout(2_000) { source.started.await() }
            screenshotter.release()
            source.deliver.complete(Unit)
            assertNull(withTimeout(2_000) { capture.await() })
            assertTrue(bitmap.isRecycled)
            assertEquals(1, source.releases.get())
        } finally {
            source.deliver.complete(Unit)
            capture.cancelAndJoin()
            screenshotter.release()
            if (!bitmap.isRecycled) bitmap.recycle()
        }
    }

    @Test fun callerCancellationRecyclesAnUnclaimedAccessibilityBitmap() = runBlocking {
        val bitmap = Bitmap.createBitmap(1, 1, Bitmap.Config.ARGB_8888)
        val source = DeferredAccessibility(bitmap)
        val screenshotter = ShizukuScreenshotter(source, { false }, { error("Accessibility is ready") })
        val capture = async { screenshotter.capture() }
        try {
            withTimeout(2_000) { source.started.await() }
            capture.cancel()
            source.deliver.complete(Unit)
            withTimeout(2_000) { capture.cancelAndJoin() }
            assertTrue(capture.isCancelled)
            assertTrue(bitmap.isRecycled)
        } finally {
            source.deliver.complete(Unit)
            capture.cancelAndJoin()
            screenshotter.release()
            if (!bitmap.isRecycled) bitmap.recycle()
        }
    }

    private fun shellScreenshotter(create: (Array<String>) -> Process?) = ShizukuScreenshotter(
        object : Screenshotter {
            override val isReady = false
            override suspend fun capture(): Bitmap? = null
            override fun release() = Unit
        }, { true }, create, ShizukuCaptureProcessRunner { child, _ ->
            (child as CompletedProcess).finished = true
            true
        },
    )

    private class DeferredAccessibility(private val bitmap: Bitmap) : Screenshotter {
        val started = CompletableDeferred<Unit>()
        val deliver = CompletableDeferred<Unit>()
        val releases = AtomicInteger()
        override val isReady = true
        override suspend fun capture(): Bitmap = withContext(NonCancellable) {
            started.complete(Unit)
            deliver.await()
            bitmap
        }
        override fun release() { releases.incrementAndGet() }
    }

    private class CompletedProcess(bytes: ByteArray) : Process() {
        private val stdout = ByteArrayInputStream(bytes)
        private val stderr = ByteArrayInputStream(byteArrayOf())
        private val stdin = ByteArrayOutputStream()
        val destroys = AtomicInteger()
        @Volatile var finished = false
        override fun getInputStream() = stdout
        override fun getErrorStream() = stderr
        override fun getOutputStream() = stdin
        override fun waitFor(): Int = error("Use the remote timed waiter")
        override fun exitValue(): Int { check(finished); return 0 }
        override fun destroy() { destroys.incrementAndGet() }
    }
}
