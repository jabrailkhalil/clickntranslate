package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dagger.hilt.EntryPoints
import dagger.hilt.android.internal.managers.ServiceComponentManager
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.PaddleModelVersion
import dev.clickn.translate.data.Settings
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureService_GeneratedInjector
import java.io.File
import java.text.Normalizer
import java.util.Locale
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Explicit real detector+Arabic recognizer+paragraph regression; installed models, no downloads. */
@RunWith(AndroidJUnit4::class)
class PaddleArabicParagraphIntegrationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()

    @Test fun ownedArabicPageKeepsBothCompleteParagraphsMixedOcrWordAndEnglishButton() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("paddleArabic") == "true")
        val settings = Settings(ocrEngine = OcrEngineKind.PADDLE_ONNX,
            paddleModelVersion = PaddleModelVersion.V5_ARABIC, sourceLang = "auto", targetLang = "ru",
            mergeAdjacentBlocks = false)
        val image = instrumentation.context.assets.open("tesseract-probe/owned-arabic-screen.png").use {
            requireNotNull(BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply {
                inPreferredConfig = Bitmap.Config.ARGB_8888
                inScaled = false
            }))
        }
        try {
            val blocks = withTimeout(90_000) { applicationBoundEngine().recognize(image, settings.ocrEngine, settings) }
            val report = JSONObject().put("fixtureOnly", true).put("model", settings.paddleModelVersion.name)
                .put("width", image.width).put("height", image.height).put("mergeAdjacentBlocks", false)
                .put("blocks", JSONArray(blocks.map { block -> JSONObject().put("text", block.text)
                    .put("language", block.recognizedLanguage).put("orientation", block.layoutOrientation?.name)
                    .put("granularity", block.regionGranularity.name).put("confidence", block.confidence)
                    .put("box", rect(block.boundingBox)).put("sourceBoxes", JSONArray(block.sourceBoxes.map(::rect))) }))
            val diagnostic = report.toString(2)
            val directory = requireNotNull(instrumentation.targetContext.getExternalFilesDir("paddle-arabic-qa"))
            check(directory.isDirectory || directory.mkdirs())
            File(directory, "result.json").writeText(diagnostic)
            println(diagnostic)
            assertFalse("Caller-owned fixture was recycled.\n$diagnostic", image.isRecycled)
            val arabic = blocks.filter { it.recognizedLanguage == "ar" }.sortedBy { it.boundingBox.top }
            assertEquals("Both independent Arabic paragraphs must remain whole.\n$diagnostic", 2, arabic.size)
            assertEquals(diagnostic, normalized("تجري الأنهار الهادئة بين الجبال، وتصل إلى قرية صغيرة يسكنها أناس طيبون."),
                normalized(arabic[0].text))
            assertEquals("All three middle rows and the embedded Latin token must reach one MT unit.\n$diagnostic",
                normalized("يقرأ الثعلب الصغير كتابًا عن السفر كل مساء، ويستخدم كلمة OCR لوصف التعرف على النص."),
                normalized(arabic[1].text))
            arabic.forEach { block ->
                assertEquals(diagnostic, TextOrientation.HORIZONTAL_RTL, block.layoutOrientation)
                assertEquals(diagnostic, TextRegionGranularity.PARAGRAPH, block.regionGranularity)
                assertTrue("Original line erasure boxes must survive paragraph construction.\n$diagnostic", block.sourceBoxes.size >= 3)
            }
            assertTrue(diagnostic, arabic[0].boundingBox.bottom < arabic[1].boundingBox.top)
            val english = blocks.singleOrNull { normalized(it.text) == "share owned photo to clickn qa" }
            assertNotNull("English UI text must remain an independent readable result.\n$diagnostic", english)
            assertEquals(diagnostic, "en", english!!.recognizedLanguage)
            assertEquals(diagnostic, TextOrientation.HORIZONTAL_LTR, english.layoutOrientation)
            assertTrue(diagnostic, arabic[1].boundingBox.bottom < english.boundingBox.top)
        } finally { if (!image.isRecycled) image.recycle() }
    }

    /** Fields only: no real Service lifecycle, capture session or shared-engine close. */
    private fun applicationBoundEngine(): OcrEngine {
        val application = instrumentation.targetContext.applicationContext
        val builder = EntryPoints.get(application,
            ServiceComponentManager.ServiceComponentBuilderEntryPoint::class.java).serviceComponentBuilder()
        val shell = CaptureService()
        (builder.service(shell).build() as CaptureService_GeneratedInjector).injectCaptureService(shell)
        return shell.ocrEngine
    }

    private fun normalized(text: String): String = Normalizer.normalize(text, Normalizer.Form.NFD)
        .replace(Regex("\\p{M}+"), "").replace("ـ", "").replace(Regex("[\\p{P}\\s]+"), " ")
        .trim().lowercase(Locale.ROOT)

    private fun rect(rect: android.graphics.Rect) = JSONArray(listOf(rect.left, rect.top, rect.right, rect.bottom))
}
