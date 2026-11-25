package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Typeface
import android.os.Build
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.googlecode.tesseract.android.ResultIterator
import com.googlecode.tesseract.android.TessBaseAPI
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.download.ModelFileDownloader
import java.io.File
import java.nio.file.Files
import java.util.Comparator
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Real Android shaping and native ara+eng. Only explicit -e downloadModels true allows download. */
@RunWith(AndroidJUnit4::class)
class TesseractArabicOcrIntegrationTest {
    private val instrumentation = InstrumentationRegistry.getInstrumentation()
    private val context = instrumentation.targetContext

    @Test fun actualArabicEnglishParagraphsKeepLogicalTextIndependentBoundsAndOfflineReuse() = runBlocking {
        assumeTrue("Native OCR requires explicitly authorized model download", downloadModels())
        withOwnedModels { models, requests ->
            val image = fixture()
            val engine = TesseractOcrEngine(models)
            try {
                models.download()
                assertTrue(models.state.value.ready)
                val before = requests.get()
                val blocks = engine.recognize(image, OcrEngineKind.TESSERACT_ARABIC)
                writeFixture(image, blocks)
                if (nativeDiagnostics()) writeNativeFixtureDiagnostics(models, image)
                val arabic = blocks.singleOrNull { it.text.contains("الشمس") && it.text.contains("الجبال") }
                assertNotNull("Native OCR missed the connected Arabic paragraph; see saved raw JSON", arabic)
                assertTrue("Arabic words were visually reversed", arabic!!.text.contains("الوديان"))
                assertFalse(arabic.text.contains("سمشلا"))
                assertEquals("ar", arabic.recognizedLanguage)
                assertEquals(TextOrientation.HORIZONTAL_RTL, arabic.layoutOrientation)
                val mixed = blocks.singleOrNull { it.text.contains("Android") && arabicLetters(it.text) > 5 }
                assertNotNull("Mixed Arabic/English text was not retained in one native paragraph", mixed)
                val english = blocks.singleOrNull { it.text.contains("Bright", true) && it.text.contains("valleys", true) }
                assertNotNull("Native eng model missed the independent English paragraph", english)
                assertEquals("en", english!!.recognizedLanguage)
                assertTrue(arabic.boundingBox.bottom < mixed!!.boundingBox.top)
                assertTrue(mixed.boundingBox.bottom < english.boundingBox.top)
                assertFalse(arabic.text.contains("Bright"))
                assertTrue(blocks.all { it.regionGranularity == TextRegionGranularity.PARAGRAPH && it.sourceBoxes.isNotEmpty() })
                assertTrue(blocks.all { it.boundingBox.left >= 0 && it.boundingBox.top >= 0 && it.boundingBox.right <= image.width && it.boundingBox.bottom <= image.height && !it.boundingBox.isEmpty })
                assertEquals("Recognition attempted a model download", before, requests.get())
                assertFalse("Recognition recycled caller-owned pixels", image.isRecycled)
                assertFalse(engine.recognizing)
            } finally { engine.close(); image.recycle() }
        }
    }

    @Test fun cancellationDrainsTheRealNativeWorkerAndTheEngineCanRecognizeAgain() = runBlocking {
        assumeTrue("Native cancellation requires explicitly authorized model download", downloadModels())
        withOwnedModels { models, requests ->
            models.download()
            val engine = TesseractOcrEngine(models)
            val image = Bitmap.createBitmap(1800, 3600, Bitmap.Config.ARGB_8888)
            val canvas = Canvas(image).apply { drawColor(Color.WHITE) }
            repeat(32) { draw(canvas, "تشرق الشمس فوق الجبال وتنساب الأنهار في الوديان.", 60, 60 + it * 105, 1680, 55f, true) }
            val published = AtomicBoolean()
            try {
                val before = requests.get()
                val job = async(Dispatchers.Default) { engine.recognize(image, OcrEngineKind.TESSERACT_ARABIC).also { published.set(true) } }
                // This flag is set only by TessBaseAPI's actual native ProgressNotifier,
                // not by scheduling the worker or entering the call's preparatory phase.
                withTimeout(10_000) { while (!engine.nativeProgressSeen) delay(20) }
                withTimeout(15_000) { job.cancelAndJoin() }
                assertFalse("A cancelled partial OCR result escaped", published.get())
                assertFalse(engine.recognizing)
                assertFalse("Caller bitmap was recycled during cancellation", image.isRecycled)
                val next = fixture()
                try {
                    val recovered = engine.recognize(next, OcrEngineKind.TESSERACT_ARABIC)
                    assertTrue("Cancelled engine retained ownership", recovered.any { it.text.contains("الشمس") })
                } finally { next.recycle() }
                assertEquals(before, requests.get())
                assertTrue(models.state.value.ready)
            } finally { engine.close(); image.recycle() }
        }
    }

    @Test fun missingModelsRejectRecognitionWithoutStartingAnyNetworkOrNativeTask() = runBlocking {
        withOwnedModels { models, requests ->
            models.refresh()
            val engine = TesseractOcrEngine(models)
            val image = fixture()
            try {
                try { engine.recognize(image, OcrEngineKind.TESSERACT_ARABIC); fail("Missing models were silently accepted") }
                catch (error: TesseractModelException) { assertEquals(TesseractModelFailure.MISSING, error.failure) }
                assertEquals(0, requests.get()); assertFalse(engine.recognizing)
                assertFalse(image.isRecycled)
            } finally { engine.close(); image.recycle() }
        }
    }

    private suspend fun withOwnedModels(action: suspend (TesseractModelStore, AtomicInteger) -> Unit) {
        val owned = Files.createTempDirectory(context.filesDir.toPath(), "qa-tesseract-").toFile()
        val requests = AtomicInteger()
        val client = OkHttpClient.Builder().addInterceptor { chain -> requests.incrementAndGet(); chain.proceed(chain.request()) }.build()
        val store = TesseractModelStore(owned, ModelFileDownloader(client), TesseractModelFiles.models)
        try { action(store, requests) } finally {
            try { withContext(NonCancellable + Dispatchers.IO) {
                store.delete()
                Files.walk(owned.toPath()).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::deleteIfExists) }
            } } finally {
                client.dispatcher.cancelAll(); client.connectionPool.evictAll(); client.dispatcher.executorService.shutdown()
            }
        }
    }

    private fun fixture(): Bitmap = Bitmap.createBitmap(1800, 1500, Bitmap.Config.ARGB_8888).also { image ->
        val canvas = Canvas(image).apply { drawColor(Color.WHITE) }
        draw(canvas, "تشرق الشمس فوق الجبال\nوتنساب الأنهار في الوديان الهادئة.", 120, 120, 1560, 70f, true)
        draw(canvas, "هذا نص عربي مع Android يعمل على الهاتف.", 120, 600, 1560, 68f, true)
        draw(canvas, "Bright rivers run through quiet\nvalleys.", 120, 1050, 1560, 65f, false)
    }

    private fun draw(canvas: Canvas, text: String, left: Int, top: Int, width: Int, size: Float, rtl: Boolean) {
        val paint = TextPaint(android.graphics.Paint.ANTI_ALIAS_FLAG).apply { color = Color.BLACK; textSize = size; typeface = Typeface.create("sans-serif", Typeface.NORMAL) }
        val layout = StaticLayout.Builder.obtain(text, 0, text.length, paint, width).setIncludePad(false)
            .setAlignment(Layout.Alignment.ALIGN_NORMAL)
            .setTextDirection(if (rtl) TextDirectionHeuristics.FIRSTSTRONG_RTL else TextDirectionHeuristics.FIRSTSTRONG_LTR).build()
        canvas.save(); canvas.translate(left.toFloat(), top.toFloat()); layout.draw(canvas); canvas.restore()
    }

    private fun writeFixture(image: Bitmap, blocks: List<TextBlock>) {
        val directory = requireNotNull(context.getExternalFilesDir("qa"))
        check(directory.isDirectory || directory.mkdirs())
        File(directory, "arabic-english-ocr-fixture.png").outputStream().use { check(image.compress(Bitmap.CompressFormat.PNG, 100, it)) }
        val report = JSONObject().put("sdk", Build.VERSION.SDK_INT).put("nativeLanguages", "ara+eng")
            .put("arabicModelSource", "tessdata_best").put("arabicModelRevision", TesseractModelFiles.ARABIC_REVISION)
            .put("englishModelRevision", TesseractModelFiles.ENGLISH_REVISION).put("modelProfile", TesseractModelFiles.REVISION)
            .put("fixtureOnly", true).put("imageWidth", image.width).put("imageHeight", image.height)
            .put("paragraphs", JSONArray(blocks.map { block -> JSONObject().put("text", block.text).put("language", block.recognizedLanguage)
                .put("direction", block.layoutOrientation?.name).put("confidence", block.confidence)
                .put("parentRegionId", block.parentRegionId).put("granularity", block.regionGranularity.name)
                .put("box", JSONArray(listOf(block.boundingBox.left, block.boundingBox.top, block.boundingBox.right, block.boundingBox.bottom)))
                .put("sourceBoxes", JSONArray(block.sourceBoxes.map { JSONArray(listOf(it.left, it.top, it.right, it.bottom)) })) }))
        File(directory, "arabic-english-ocr-result-api${Build.VERSION.SDK_INT}.json").writeText(report.toString(2))
    }

    /** Only this synthetic fixture is recorded. No production screen, OCR hook or relaxed assertion. */
    private suspend fun writeNativeFixtureDiagnostics(models: TesseractModelStore, fixture: Bitmap) {
        models.withOcrModels { path -> withContext(Dispatchers.Default) {
            val directory = requireNotNull(context.getExternalFilesDir("qa"))
            check(directory.isDirectory || directory.mkdirs())
            for ((label, mode) in listOf("auto" to TessBaseAPI.PageSegMode.PSM_AUTO,
                "sparse" to TessBaseAPI.PageSegMode.PSM_SPARSE_TEXT,
                "single-column" to TessBaseAPI.PageSegMode.PSM_SINGLE_COLUMN,
                "single-block" to TessBaseAPI.PageSegMode.PSM_SINGLE_BLOCK,
                "auto-dpi300" to TessBaseAPI.PageSegMode.PSM_AUTO,
                "auto-dpi150" to TessBaseAPI.PageSegMode.PSM_AUTO)) {
                val image = requireNotNull(fixture.copy(Bitmap.Config.ARGB_8888, false))
                val native = TessBaseAPI()
                try {
                    check(native.init(path, "ara+eng", TessBaseAPI.OEM_LSTM_ONLY))
                    native.pageSegMode = mode
                    val dpi = when (label) { "auto-dpi300" -> "300"; "auto-dpi150" -> "150"; else -> null }
                    if (dpi != null) check(native.setVariable("user_defined_dpi", dpi)) { "Native user_defined_dpi was rejected" }
                    native.setImage(image)
                    val hocr = native.getHOCRText(0).orEmpty()
                    val text = native.getUTF8Text().orEmpty()
                    check(hocr.length <= 1_000_000 && text.length <= 100_000)
                    val prefix = "arabic-english-native-$label-api${Build.VERSION.SDK_INT}"
                    File(directory, "$prefix.hocr.html").writeText(hocr)
                    File(directory, "$prefix-full-utf8.txt").writeText(text)
                    val report = JSONObject().put("fixtureOnly", true).put("sdk", Build.VERSION.SDK_INT)
                        .put("arabicModelSource", "tessdata_best").put("arabicModelRevision", TesseractModelFiles.ARABIC_REVISION)
                        .put("englishModelRevision", TesseractModelFiles.ENGLISH_REVISION).put("modelProfile", TesseractModelFiles.REVISION)
                        .put("nativeLanguages", "ara+eng").put("pageSegMode", mode)
                        .put("requestedUserDefinedDpi", dpi ?: JSONObject.NULL)
                        .put("width", image.width).put("height", image.height)
                    val iterator = native.resultIterator
                    if (iterator != null) try {
                        report.put("beforeBegin", nativePosition(iterator))
                        iterator.begin()
                        report.put("afterBegin", nativePosition(iterator))
                        val paragraphs = JSONArray()
                        do {
                            check(paragraphs.length() < 128)
                            paragraphs.put(nativePosition(iterator))
                        } while (iterator.next(TessBaseAPI.PageIteratorLevel.RIL_PARA))
                        report.put("paragraphTraversal", paragraphs)
                        iterator.begin()
                        val lines = JSONArray()
                        do {
                            check(lines.length() < 128)
                            lines.put(nativePosition(iterator))
                        } while (iterator.next(TessBaseAPI.PageIteratorLevel.RIL_TEXTLINE))
                        report.put("lineTraversal", lines)
                    } finally { iterator.delete() }
                    File(directory, "$prefix-iterator.json").writeText(report.toString(2))
                } finally { try { native.recycle() } finally { image.recycle() } }
            }
        } }
    }

    private fun nativePosition(iterator: ResultIterator): JSONObject = JSONObject().also { position ->
        for ((label, level) in listOf("block" to TessBaseAPI.PageIteratorLevel.RIL_BLOCK,
            "paragraph" to TessBaseAPI.PageIteratorLevel.RIL_PARA,
            "line" to TessBaseAPI.PageIteratorLevel.RIL_TEXTLINE,
            "word" to TessBaseAPI.PageIteratorLevel.RIL_WORD)) {
            val text = iterator.getUTF8Text(level).orEmpty()
            check(text.length <= 100_000)
            position.put(label, JSONObject().put("text", text)
                .put("box", JSONArray(iterator.getBoundingBox(level).toList()))
                .put("atBeginning", iterator.isAtBeginningOf(level))
                .put("confidence", iterator.confidence(level)))
        }
    }
    private fun arabicLetters(text: String) = text.codePoints().filter { Character.isLetter(it) && Character.UnicodeScript.of(it) == Character.UnicodeScript.ARABIC }.count()
    private fun downloadModels() = InstrumentationRegistry.getArguments().getString("downloadModels") == "true"
    private fun nativeDiagnostics() = InstrumentationRegistry.getArguments().getString("nativeDiagnostics") == "true"
}
