package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.googlecode.tesseract.android.ResultIterator
import com.googlecode.tesseract.android.TessBaseAPI
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.download.ModelFileDownloader
import java.io.File
import java.nio.file.Files
import java.util.Comparator
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Explicit diagnostic of one owned screen; default suites skip it. Never downloads models. */
@RunWith(AndroidJUnit4::class)
class TesseractOwnedScreenProbeTest {
    @Test fun compareNativePageSegmentationWithApplicationParagraphs() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("tessProbe") == "true")
        val cropOnly = InstrumentationRegistry.getArguments().getString("tessProbeCrop") == "true"
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val directory = context.ocrFixtureOutput(if (cropOnly) "tess-probe-crop-result" else "tess-probe-result")
        val input = requireNotNull(context.getExternalFilesDir("tess-probe-input"))
        val owned = Files.createTempDirectory(context.cacheDir.toPath(), "owned-screen-tess-").toFile()
        val modelDirectory = File(owned, "verified-${TesseractModelFiles.REVISION}/tessdata").apply { mkdirs() }
        val client = OkHttpClient.Builder().addInterceptor { error("This probe must never use the network") }.build()
        val models = TesseractModelStore(owned, ModelFileDownloader(client), TesseractModelFiles.models)
        val fullImage = instrumentation.context.assets.open("tesseract-probe/owned-arabic-screen.png").use {
            requireNotNull(BitmapFactory.decodeStream(it))
        }
        val image = if (cropOnly) Bitmap.createBitmap(fullImage, 55, 1340, 1145, 610) else fullImage
        val engine = TesseractOcrEngine(models)
        try {
            TesseractModelFiles.models.forEach { spec ->
                val supplied = File(input, "${spec.language}.traineddata")
                check(TesseractModelFiles.verified(supplied, spec)) { "Missing or unverified explicit ${spec.language} model input" }
                supplied.copyTo(File(modelDirectory, supplied.name))
            }
            val report = JSONObject().put("fixtureOnly", true).put("width", image.width).put("height", image.height)
                .put("modelProfile", TesseractModelFiles.REVISION).put("cropOnly", cropOnly)
            if (cropOnly) report.put("sourceCrop", JSONArray(listOf(55, 1340, 1200, 1950)))
            val blocks = if (cropOnly) emptyList() else engine.recognize(image, OcrEngineKind.TESSERACT_ARABIC)
            report.put("applicationAutoParagraphs", JSONArray(blocks.map { block ->
                JSONObject().put("text", block.text).put("confidence", block.confidence)
                    .put("box", JSONArray(listOf(block.boundingBox.left, block.boundingBox.top, block.boundingBox.right, block.boundingBox.bottom)))
            }))
            models.withOcrModels { path ->
                val modes = JSONArray()
                val requestedModes = if (cropOnly) listOf("single-block-crop" to TessBaseAPI.PageSegMode.PSM_SINGLE_BLOCK)
                    else listOf("auto" to TessBaseAPI.PageSegMode.PSM_AUTO, "sparse" to TessBaseAPI.PageSegMode.PSM_SPARSE_TEXT)
                for ((label, mode) in requestedModes) {
                    val native = TessBaseAPI()
                    try {
                        check(native.init(path, "ara+eng", TessBaseAPI.OEM_LSTM_ONLY))
                        native.pageSegMode = mode
                        native.setImage(image)
                        val hocr = native.getHOCRText(0).orEmpty()
                        val utf8 = native.getUTF8Text().orEmpty()
                        check(hocr.length <= 1_000_000 && utf8.length <= 100_000)
                        File(directory, "$label.hocr.html").writeText(hocr)
                        File(directory, "$label.utf8.txt").writeText(utf8)
                        val result = JSONObject().put("name", label).put("mode", mode).put("utf8", utf8)
                        val iterator = native.resultIterator
                        if (iterator != null) try {
                            result.put("paragraphs", traversal(iterator, TessBaseAPI.PageIteratorLevel.RIL_PARA))
                            result.put("lines", traversal(iterator, TessBaseAPI.PageIteratorLevel.RIL_TEXTLINE))
                        } finally { iterator.delete() }
                        modes.put(result)
                    } finally { native.recycle() }
                }
                report.put("nativeModes", modes)
            }
            File(directory, "result.json").writeText(report.toString(2))
            println("OWNED_TESS_PROBE applicationParagraphs=${blocks.size} output=${directory.absolutePath}")
        } finally {
            engine.close()
            image.recycle()
            if (image !== fullImage) fullImage.recycle()
            Files.walk(owned.toPath()).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::deleteIfExists) }
            client.dispatcher.executorService.shutdown()
            client.connectionPool.evictAll()
        }
    }

    private fun traversal(iterator: ResultIterator, level: Int): JSONArray {
        val output = JSONArray()
        iterator.begin()
        do {
            check(output.length() < 200)
            output.put(JSONObject().put("text", iterator.getUTF8Text(level).orEmpty())
                .put("box", JSONArray(iterator.getBoundingBox(level).toList()))
                .put("atParagraphBeginning", iterator.isAtBeginningOf(TessBaseAPI.PageIteratorLevel.RIL_PARA))
                .put("confidence", iterator.confidence(level)))
        } while (iterator.next(level))
        return output
    }
}
