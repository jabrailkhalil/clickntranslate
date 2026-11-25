package dev.clickn.translate.capture

import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PixelFormat
import android.media.ImageReader
import android.os.Bundle
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dagger.hilt.EntryPoints
import dagger.hilt.android.internal.managers.ServiceComponentManager
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.ocr.OcrEngine
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureService_GeneratedInjector
import dev.clickn.translate.translate.CommunityTranslationClient
import java.net.InetAddress
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import rikka.shizuku.Shizuku

/** Physical-device probes. Both inputs are generated here; neither path can read the user's display. */
@RunWith(AndroidJUnit4::class)
class OwnedSurfaceCaptureSoakIntegrationTest {
    private val args get() = InstrumentationRegistry.getArguments()
    private data class Page(val text: String, val translation: String, val shade: Int)

    @Test fun repeatedOwnedPagesPassTheRealOcrAndTranslationAdapter() = runBlocking {
        assumeTrue("Opt in with -e ownedCaptureSoak true", args.getString("ownedCaptureSoak") == "true")
        val seconds = (args.getString("ownedSeconds") ?: "120").toInt()
        require(seconds in 10..600) { "Use a duration of 10 to 600 seconds" }
        val pages = listOf(Page("Blue door", "Синяя дверь", 255),
            Page("Green boat", "Зелёная лодка", 162), Page("Golden sun", "Золотое солнце", 216))
        val pageCount = (seconds / 4).coerceAtLeast(4)
        val holdMs = seconds * 1000L / pageCount
        val ocr = targetOcr()
        val client = OkHttpClient()
        val translator = CommunityTranslationClient(client, Json)
        try {
            MockWebServer().use { server ->
                server.start(InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)), 0)
                val settings = Settings(sourceLang = "en", targetLang = "ru", ocrEngine = OcrEngineKind.ML_KIT_LATIN,
                    translatorEngine = TranslatorEngine.LIBRETRANSLATE, libreTranslateApiKey = "",
                    libreTranslateBaseUrl = "http://127.0.0.1:${server.port}")
                val policy = SettledPagePolicy()
                var anchor: SettledPageFrame? = null
                var frameCount = 0
                var longestOcrMs = 0L
                val startedAt = SystemClock.elapsedRealtime()
                withTimeout(seconds * 1000L + 90_000L) {
                    ImageReader.newInstance(640, 240, PixelFormat.RGBA_8888, 2).use { source ->
                        repeat(pageCount) { index ->
                            val page = pages[index % pages.size]
                            val pageStart = SystemClock.elapsedRealtime()
                            var submitted = false
                            var observedAfterResult = false
                            do {
                                val bitmap = readOwnedPage(source, page)
                                try {
                                    frameCount++
                                    val sample = LoopFrameFingerprintFactory.createObservation(bitmap, 1, emptyList())
                                    val similarity = anchor?.let { SettledPageVisualPolicy.similarity(it, sample) }
                                    val decision = policy.observe(
                                        sameAsAnchor = similarity != null && similarity >= LoopFrameChangePolicy.DEFAULT_SIMILARITY_THRESHOLD,
                                        contextUnchanged = true, nowMs = SystemClock.elapsedRealtime(),
                                        stableDurationMs = settings.loopTextStableDurationMs,
                                    )
                                    if (decision.replaceAnchor) anchor = sample
                                    if (submitted) observedAfterResult = true
                                    if (decision.ready) {
                                        assertFalse("Duplicate submission for page $index", submitted)
                                        assertTrue(policy.claim(decision.revision))
                                        val ocrStart = SystemClock.elapsedRealtime()
                                        val blocks = withTimeout(45_000) { ocr.recognize(bitmap, settings.ocrEngine, settings) }
                                        longestOcrMs = maxOf(longestOcrMs, SystemClock.elapsedRealtime() - ocrStart)
                                        val text = extractedCardText(blocks, settings).trim()
                                        assertEquals("OCR on synthetic page $index", page.text, text)
                                        server.enqueue(MockResponse().setHeader("Content-Type", "application/json")
                                            .setBody(JSONObject().put("translatedText", page.translation).toString()))
                                        assertEquals(page.translation, translator.translate(text, settings))
                                        val request = requireNotNull(server.takeRequest(2, TimeUnit.SECONDS))
                                        assertEquals("POST", request.method)
                                        assertEquals("/translate", request.path)
                                        val json = JSONObject(request.body.readUtf8())
                                        assertEquals(page.text, json.getString("q"))
                                        assertEquals("en", json.getString("source"))
                                        assertEquals("ru", json.getString("target"))
                                        submitted = true
                                    }
                                } finally {
                                    bitmap.recycle()
                                }
                                delay(180)
                            } while ((!observedAfterResult || SystemClock.elapsedRealtime() - pageStart < holdMs) &&
                                SystemClock.elapsedRealtime() - pageStart < holdMs + 50_000L)
                            assertTrue("No successful translation for page $index", submitted)
                            assertTrue("No stable observation after page $index translated", observedAfterResult)
                        }
                    }
                }
                assertEquals(pageCount, server.requestCount)
                report("ownedCaptureSoak", "elapsedMs=${SystemClock.elapsedRealtime() - startedAt} " +
                    "frames=$frameCount pages=$pageCount translations=${server.requestCount} maxOcrMs=$longestOcrMs")
            }
        } finally {
            client.connectionPool.evictAll()
            client.dispatcher.executorService.shutdown()
        }
    }

    private suspend fun readOwnedPage(source: ImageReader, page: Page): Bitmap {
        val surface = source.surface
        val canvas = surface.lockCanvas(null)
        try {
            canvas.drawColor(Color.rgb(page.shade, page.shade, page.shade))
            val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK; textSize = 58f }
            canvas.drawText(page.text, 44f, 145f, paint)
        } finally {
            surface.unlockCanvasAndPost(canvas)
        }
        return withTimeout(4_000) {
            var next = source.acquireNextImage()
            while (next == null) {
                delay(10)
                next = source.acquireNextImage()
            }
            next.use { image ->
                val plane = image.planes.single()
                assertEquals(4, plane.pixelStride)
                val pixels = packImageRows(plane.buffer, image.width * plane.pixelStride, plane.rowStride, image.height)
                Bitmap.createBitmap(image.width, image.height, Bitmap.Config.ARGB_8888).also { it.copyPixelsFromBuffer(pixels) }
            }
        }
    }

    private fun targetOcr(): OcrEngine {
        val application = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext
        val builder = EntryPoints.get(application,
            ServiceComponentManager.ServiceComponentBuilderEntryPoint::class.java).serviceComponentBuilder()
        val service = CaptureService()
        (builder.service(service).build() as CaptureService_GeneratedInjector).injectCaptureService(service)
        return service.ocrEngine
    }

    @Test fun authorizedShizukuTransportDecodesOnlySyntheticPixels() = runBlocking {
        assumeTrue("Opt in with -e shizukuTransport true", args.getString("shizukuTransport") == "true")
        val deadline = SystemClock.elapsedRealtime() + 5_000L
        while (!Shizuku.pingBinder() && SystemClock.elapsedRealtime() < deadline) delay(100)
        assertTrue("Shizuku service is not reachable by the app in this Android user", Shizuku.pingBinder())
        assertEquals("The app has no Shizuku authorization in this Android user",
            PackageManager.PERMISSION_GRANTED, Shizuku.checkSelfPermission())
        val uid = Shizuku.getUid()
        assertTrue("Expected shell or root Shizuku service", uid == 2000 || uid == 0)

        val fixture = ByteBuffer.allocate(24).order(ByteOrder.LITTLE_ENDIAN)
            .putInt(2).putInt(1).putInt(PixelFormat.RGBA_8888).putInt(0)
            .put(byteArrayOf(-1, 0, 0, -1, 0, -1, 0, -1)).array()
        // Android's printf builtin accepts these static octal bytes; it reads no files or screen.
        val octets = fixture.joinToString("") { "\\" + (it.toInt() and 255).toString(8).padStart(3, '0') }
        val method = Shizuku::class.java.getDeclaredMethod("newProcess", Array<String>::class.java,
            Array<String>::class.java, String::class.java).apply { isAccessible = true }
        val noAccessibility = object : Screenshotter {
            override val isReady = false
            override suspend fun capture(): Bitmap? = error("Accessibility display capture must never be used")
            override fun release() = Unit
        }
        var requests = 0
        val screenshotter = ShizukuScreenshotter(noAccessibility, { true }, { requested ->
            require(requested.contentEquals(arrayOf("screencap"))) { "Unexpected image route" }
            requests++
            method.invoke(null, arrayOf("/system/bin/sh", "-c", "printf '$octets'"), null, null) as Process
        })
        try {
            assertTrue(screenshotter.isReady)
            repeat(3) {
                val bitmap = screenshotter.capture()
                assertNotNull("Could not decode synthetic frame through the authorized shell", bitmap)
                requireNotNull(bitmap)
                try {
                    assertEquals(2, bitmap.width)
                    assertEquals(1, bitmap.height)
                    assertEquals(Color.RED, bitmap.getPixel(0, 0))
                    assertEquals(Color.GREEN, bitmap.getPixel(1, 0))
                } finally {
                    bitmap.recycle()
                }
            }
        } finally {
            screenshotter.release()
        }
        assertFalse(screenshotter.isReady)
        assertNull(screenshotter.capture())
        assertEquals(3, requests)
        report("shizukuTransport", "uid=$uid version=${Shizuku.getVersion()} generatedFrames=$requests")
    }

    private fun report(key: String, value: String) {
        InstrumentationRegistry.getInstrumentation().addResults(Bundle().apply { putString(key, value) })
    }
}
