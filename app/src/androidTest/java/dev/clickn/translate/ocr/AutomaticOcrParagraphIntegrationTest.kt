package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dagger.hilt.EntryPoints
import dagger.hilt.android.internal.managers.ServiceComponentManager
import dev.clickn.translate.capture.extractedCardText
import dev.clickn.translate.data.MergeStrength
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.data.Settings
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureService_GeneratedInjector
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Real Auto OCR over a clean, owned source screenshot; no MT, downloads or settings writes. */
@RunWith(AndroidJUnit4::class)
class AutomaticOcrParagraphIntegrationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    @Test fun twoColumnPixelsReachTheExtractionCardInReadingOrder() =
        checkColumnExtraction(OcrEngineKind.ML_KIT_LATIN)

    @Test fun automaticOcrKeepsColumnOrderAfterCombiningRecognizerPasses() =
        checkColumnExtraction(OcrEngineKind.ML_KIT_AUTO)

    private fun checkColumnExtraction(kind: OcrEngineKind) = runBlocking {
        val image = Bitmap.createBitmap(1400, 420, Bitmap.Config.ARGB_8888)
        val settings = Settings(ocrEngine = kind,
            sourceLang = "en", targetLang = "ru", renderMode = RenderMode.FLOATING_WINDOW,
            mergeAdjacentBlocks = true, mergeStrength = MergeStrength.ALL)
        try {
            val canvas = Canvas(image)
            canvas.drawColor(Color.WHITE)
            val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK; textSize = 40f }
            val left = listOf("Quiet rivers flow", "through the valley", "toward the sea")
            val right = listOf("Golden birds fly", "over the forest", "toward the hills")
            left.forEachIndexed { i, line -> canvas.drawText(line, 70f, 130f + 49f * i, ink) }
            right.forEachIndexed { i, line -> canvas.drawText(line, 780f, 137f + 49f * i, ink) }
            val engine = applicationBoundOcrEngine()
            val blocks = withTimeout(60_000) { engine.recognize(image, settings.ocrEngine, settings) }
            val detail = blocks.joinToString { "${it.text} @${it.boundingBox} parent=${it.parentRegionId}" }
            assertTrue("Unexpected OCR bounds: $detail", blocks.flatMap { it.sourceBoxes.ifEmpty { listOf(it.boundingBox) } }
                .all { !it.isEmpty && it.left >= 0 && it.top >= 0 && it.right <= image.width && it.bottom <= image.height })
            assertEquals(detail, (left + right).joinToString(" ").lowercase(),
                extractedCardText(blocks, settings).trim().replace(Regex("\\s+"), " ").lowercase())
            assertFalse(image.isRecycled)
            canvas.drawColor(Color.WHITE)
            val blank = withTimeout(60_000) { engine.recognize(image, settings.ocrEngine, settings) }
            assertEquals("", extractedCardText(blank, settings))
            assertFalse(image.isRecycled)
        } finally {
            if (!image.isRecycled) image.recycle()
        }
    }

    @Test fun ownedSilverAndGentlePageKeepsTwoIndependentCompleteParagraphs() = runBlocking {
        val settings = Settings(
            ocrEngine = OcrEngineKind.ML_KIT_AUTO,
            sourceLang = "en",
            targetLang = "ru",
            mergeAdjacentBlocks = false,
        )
        val image = instrumentation.context.assets.open("settled-text/gentle-page1-source.png").use { input ->
            requireNotNull(BitmapFactory.decodeStream(input, null, BitmapFactory.Options().apply {
                inPreferredConfig = Bitmap.Config.ARGB_8888
                inScaled = false
            })) { "Owned clean-source PNG could not be decoded" }
        }
        try {
            val engine = applicationBoundOcrEngine()
            val blocks = withTimeout(60_000) {
                engine.recognize(image, OcrEngineKind.ML_KIT_AUTO, settings)
            }
            val diagnostic = JSONObject()
                .put("fixture", "settled-text/gentle-page1-source.png")
                .put("width", image.width).put("height", image.height)
                .put("engine", settings.ocrEngine.name)
                .put("sourceLang", settings.sourceLang).put("targetLang", settings.targetLang)
                .put("mergeAdjacentBlocks", settings.mergeAdjacentBlocks)
                .put("blocks", JSONArray(blocks.map { block ->
                    JSONObject()
                        .put("text", block.text)
                        .put("boundingBox", rect(block.boundingBox))
                        .put("confidence", block.confidence)
                        .put("recognizedLanguage", block.recognizedLanguage ?: JSONObject.NULL)
                        .put("layoutOrientation", block.layoutOrientation?.name ?: JSONObject.NULL)
                        .put("parentRegionId", block.parentRegionId ?: JSONObject.NULL)
                        .put("regionGranularity", block.regionGranularity.name)
                        .put("sourceBoxes", JSONArray(block.sourceBoxes.map(::rect)))
                })).toString(2)
            println(diagnostic)
            assertFalse("OCR recycled its caller-owned fixture.\n$diagnostic", image.isRecycled)
            assertEquals(
                "Auto OCR must preserve independent paragraphs and attach the short wrapped ending.\n$diagnostic",
                listOf("Silver trains travel beyond the mountain.", "Gentle winds carry the autumn leaves."),
                blocks.map { it.text.replace(Regex("\\s+"), " ").trim() },
            )
        } finally {
            if (!image.isRecycled) image.recycle()
        }
    }

    @Test fun automaticOcrRetainsSeparateLatinAndCjkRegions() = runBlocking {
        val image = Bitmap.createBitmap(1080, 1100, Bitmap.Config.ARGB_8888)
        try {
            val canvas = Canvas(image)
            val ink = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                color = Color.BLACK
                textSize = 62f
            }
            canvas.drawColor(Color.WHITE)
            canvas.drawText("Quiet rivers flow.", 90f, 310f, ink)
            canvas.drawText("黄河穿过群山", 90f, 790f, ink)
            val blocks = withTimeout(60_000) {
                applicationBoundOcrEngine().recognize(image, OcrEngineKind.ML_KIT_AUTO, Settings())
            }
            assertFalse(image.isRecycled)
            assertTrue("English block lost: ${blocks.map { it.text }}", blocks.any {
                it.boundingBox.centerY() < 550 && it.text.contains("Quiet rivers flow", ignoreCase = true)
            })
            assertTrue("CJK block lost: ${blocks.map { it.text }}", blocks.any {
                it.boundingBox.centerY() > 550 && it.text.contains("群山")
            })
        } finally {
            image.recycle()
        }
    }

    /**
     * Reuse the target application's real Hilt OcrEngine binding through its existing injector.
     * This unattached shell receives fields only: no Service lifecycle, foreground operation,
     * capture session, onDestroy or shared-engine close is invoked by the test.
     */
    private fun applicationBoundOcrEngine(): OcrEngine {
        val application = instrumentation.targetContext.applicationContext
        val builder = EntryPoints.get(application,
            ServiceComponentManager.ServiceComponentBuilderEntryPoint::class.java).serviceComponentBuilder()
        val shell = CaptureService()
        val component = builder.service(shell).build()
        (component as CaptureService_GeneratedInjector).injectCaptureService(shell)
        return shell.ocrEngine
    }

    private fun rect(rect: android.graphics.Rect) = JSONArray(listOf(rect.left, rect.top, rect.right, rect.bottom))
}
