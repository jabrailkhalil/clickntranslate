package dev.clickn.translate.ocr

import android.content.ContextWrapper
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.system.Os
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import dev.clickn.translate.data.LogRepository
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.PaddleModelVersion
import dev.clickn.translate.data.RuntimeTranslationPromptContext
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.SettingsRepository
import dev.clickn.translate.data.SettingsSecretCipher
import dev.clickn.translate.data.SettingsStorage
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.download.ModelFileDownloader
import dev.clickn.translate.llm.LlamaEngineHolder
import dev.clickn.translate.llm.LlmModelInstaller
import dev.clickn.translate.llm.LlmModelKind
import dev.clickn.translate.llm.LlamaMultiSequence
import dev.clickn.translate.llm.LocalLlmDeviceCapability
import dev.clickn.translate.llm.LocalLlmSamplingPolicy
import dev.clickn.translate.translate.HyMt2PromptPolicy
import dev.clickn.translate.translate.HyMt2Translator
import dev.clickn.translate.translate.TranslationCache
import dev.clickn.translate.util.RuntimePerformanceDiagnostics
import java.io.File
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Opt-in, synthetic pixels only. OCR and translation can be rerun independently on the same phone. */
@RunWith(AndroidJUnit4::class)
class ArabicMarksIntegrationTest {
    private val runner = InstrumentationRegistry.getInstrumentation()
    private val args = InstrumentationRegistry.getArguments()
    private val root get() = File(runner.targetContext.cacheDir, "arabic-marks")
    private val version = PaddleModelVersion.V5_ARABIC

    @Test fun aSecondDetachedMarkBelowAFathaPreventsShaddaRemoval() {
        val width = 40
        val pixels = IntArray(width * 40) { Color.WHITE }
        for (x in 12..23) {
            val y = 8 - (x - 12) / 2
            pixels[y * width + x] = Color.BLACK
            pixels[(y + 1) * width + x] = Color.BLACK
        }
        for (y in 18..36) pixels[y * width + 20] = Color.BLACK
        fun clipped() = ArabicWordMarks.singleClippedStroke(pixels, width, Rect(9, 3, 30, 37),
            x = 17f, cutY = 8f, lineHeight = 40f)
        assertTrue(clipped())
        for (x in 15..21) pixels[13 * width + x] = Color.BLACK
        for (x in listOf(15, 18, 21)) pixels[12 * width + x] = Color.BLACK
        assertFalse(clipped())
    }

    private suspend fun withRepository(block: suspend (ContextWrapper, SettingsRepository, ModelFileDownloader) -> Unit) {
        assertEquals("dev.clickn.translate.debug", runner.targetContext.packageName)
        check(root.isDirectory || root.mkdirs())
        val context = object : ContextWrapper(runner.targetContext) { override fun getFilesDir() = root }
        val store = SettingsStorage(File(root, "fixture.preferences_pb"))
        val cipher = object : SettingsSecretCipher {
            override fun encrypt(plainText: String): String = error("Offline fixture")
            override fun decrypt(cipherText: String): String = error("Offline fixture")
        }
        val http = OkHttpClient.Builder().addInterceptor { chain ->
            check(args.getString("downloadModels") == "true") { "Downloads require explicit opt-in" }
            chain.proceed(chain.request())
        }.build()
        try {
            block(context, SettingsRepository(context, cipher, store.dataStore), ModelFileDownloader(http))
        } finally {
            store.closeAndJoin()
            http.connectionPool.evictAll()
            http.dispatcher.executorService.shutdown()
        }
    }

    @Test fun recognizeOwnedCards() = runBlocking {
        assumeTrue(args.getString("arabicMarks") == "true")
        val rows = JSONArray()
        val timingPages = args.getString("arabicTimingPages") == "true"
        val inputs = runner.context.assets.open("tesseract-probe/arabic-marks.tsv").bufferedReader().useLines { lines ->
            lines.map { it.split('\t', limit = 2) }.toList()
        }
        val darkControls = if (args.getString("arabicDarkControls") == "true") listOf(
            "story-angel" to "ظهر مَلَك في القصة.",
            "story-king" to "ظهر مَلِك في القصة.",
            "story-partial" to "ظهر مَلك في القصة.",
            "story-unmarked" to "ظهر ملك في القصة.",
            "new-angel" to "هذا مَلَك في الحكاية.",
            "new-king" to "هذا مَلِك في الحكاية.",
            "true-shadda" to "مَلَّكَ الأب ابنه البيت.",
            "true-shadda-medial" to "عَلَّمَ خالد الطالب.",
        ) else emptyList()
        val settings = Settings(ocrEngine = OcrEngineKind.PADDLE_ONNX, paddleModelVersion = version,
            sourceLang = "ar", targetLang = "ru", mergeAdjacentBlocks = false)
        withRepository { context, repo, downloader ->
            val installer = PaddleModelInstaller(context, downloader, repo)
            if (args.getString("downloadModels") == "true") installer.downloadAll(version).collect()
            val engine = PaddleOcrEngine(context, installer, repo, LogRepository(), ShapeAwareBubbleSessionStore())
            suspend fun record(id: String, style: String, source: String, image: Bitmap, paragraph: Int? = null) {
                try {
                    val start = android.os.SystemClock.elapsedRealtime()
                    val blocks = engine.recognize(image, settings.ocrEngine, settings)
                    val ms = android.os.SystemClock.elapsedRealtime() - start
                    val chosen = if (paragraph == null) blocks else blocks.filter { it.recognizedLanguage == "ar" }
                        .sortedBy { it.boundingBox.top }.drop(paragraph).take(1)
                    val observed = chosen.joinToString(" ") { it.text }.replace(Regex("\\s+"), " ").trim()
                    rows.put(JSONObject().put("id", id).put("style", style).put("source", source)
                        .put("observed", observed).put("ocrMs", ms).put("blocks", JSONArray(chosen.map { block ->
                            JSONObject().put("text", block.text).put("box", block.boundingBox.toShortString())
                        })))
                    if (args.getString("saveFixturePixels") == "true" && paragraph == null) {
                        File(root, "$id-$style.png").outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
                    }
                } finally { image.recycle() }
            }
            suspend fun recordPage(id: String, style: String) {
                val page = runner.context.assets.open("tesseract-probe/owned-arabic-screen.png").use {
                    requireNotNull(BitmapFactory.decodeStream(it))
                }
                record(id, style, "يقرأ الثعلب الصغير كتابًا عن السفر كل مساء، ويستخدم كلمة OCR لوصف التعرف على النص.", page, 1)
            }
            try {
                recordPage("fox", "page")
                for ((id, source) in inputs) for (dark in listOf(false, true)) {
                    record(id, if (dark) "dark54" else "light34", source, card(source, dark))
                }
                for ((id, source) in darkControls) for (size in listOf(38, 54, 68)) {
                    record(id, "navy$size", source, card(source, dark = true, size = size.toFloat(),
                        background = Color.rgb(27, 36, 51), foreground = Color.rgb(221, 228, 238)))
                }
                if (timingPages) repeat(3) { index ->
                    recordPage("page-$index", "warm")
                    val line = "تجري الأنهار الهادئة بين الجبال وتصل إلى قرية صغيرة يسكنها أناس طيبون"
                    record("long-$index", "warm", line, card(line, dark = true))
                }
            } finally {
                engine.close()
                File(root, "ocr.json").writeText(rows.toString(2))
            }
        }
        assertEquals(1 + inputs.size * 2 + darkControls.size * 3 + (if (timingPages) 6 else 0), rows.length())
        for (i in 0 until rows.length()) assertTrue(rows.getJSONObject(i).toString(), rows.getJSONObject(i).getString("observed").isNotBlank())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val words = row.getString("observed").split(' ')
            val matches = when (row.getString("id")) {
                "angel", "story-angel", "new-angel" -> "مَلَك" in words
                "king", "story-king", "new-king" -> words.any { it.trimEnd('َ', 'ُ', 'ِ') == "مَلِك" }
                "story-partial" -> words.any { it.trimEnd('َ', 'ُ', 'ِ') == "مَلك" }
                "story-unmarked" -> "ملك" in words
                else -> continue
            }
            assertTrue(row.toString(), matches)
        }
    }

    private fun card(source: String, dark: Boolean, size: Float = if (dark) 54f else 34f,
        background: Int = if (dark) Color.rgb(23, 23, 23) else Color.WHITE,
        foreground: Int = if (dark) Color.WHITE else Color.BLACK): Bitmap {
        val paint = TextPaint(Paint.ANTI_ALIAS_FLAG or Paint.SUBPIXEL_TEXT_FLAG).apply {
            textSize = size
            color = foreground
        }
        val width = kotlin.math.ceil(Layout.getDesiredWidth(source, paint).toDouble()).toInt() + 8
        val layout = StaticLayout.Builder.obtain(source, 0, source.length, paint, width)
            .setAlignment(Layout.Alignment.ALIGN_NORMAL).setTextDirection(TextDirectionHeuristics.RTL)
            .setIncludePad(true).build()
        check(layout.lineCount == 1)
        return Bitmap.createBitmap(width + 64, layout.height + 64, Bitmap.Config.ARGB_8888).also {
            val canvas = Canvas(it)
            canvas.drawColor(background)
            canvas.translate(32f, 32f)
            layout.draw(canvas)
        }
    }

    @Test fun translateReferenceAndOcr() = runBlocking {
        assumeTrue(args.getString("arabicMarksMt") == "true")
        val rows = JSONArray(File(root, "ocr.json").readText())
        val sources = linkedSetOf<String>()
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            sources += row.getString("source")
            sources += row.getString("observed")
        }
        withRepository { context, repo, downloader ->
            val kind = LlmModelKind.HY_MT2_1_8B_Q4_K_M
            assertEquals(kind.expectedSizeBytes, File(root, "models/llm/${kind.fileName}").length())
            val holder = LlamaEngineHolder(context, LlmModelInstaller(context, downloader, repo), LocalLlmDeviceCapability())
            val translator = HyMt2Translator(holder, TranslationCache(), RuntimePerformanceDiagnostics(LogRepository()))
            val settings = Settings(sourceLang = "ar", targetLang = "ru", translatorEngine = TranslatorEngine.LOCAL_HY_MT2,
                disableTranslationCache = true, localLlmMaxNewTokens = 128)
            val translations = JSONObject()
            try {
                for (source in sources) {
                    val output = translator.translate(source, settings).orEmpty()
                    assertTrue("Empty translation for synthetic input $source", output.isNotBlank())
                    translations.put(source, output)
                }
            } finally {
                holder.unload()
                File(root, "translations.json").writeText(translations.toString(2))
            }
        }
    }

    /** Isolate the effect of the OCR spelling from sampling variation; app settings are untouched. */
    @Test fun compareSpellingsWithGreedyDecoding() = runBlocking {
        assumeTrue(args.getString("arabicMarksGreedy") == "true")
        assertEquals("dev.clickn.translate.debug", runner.targetContext.packageName)
        val inputs = JSONArray(File(root, "spellings.json").readText())
        val kind = LlmModelKind.HY_MT2_1_8B_Q4_K_M
        val model = File(root, "models/llm/${kind.fileName}")
        assertEquals(kind.expectedSizeBytes, model.length())
        val environment = LocalLlmSamplingPolicy.nativeEnvironment(kind) + mapOf(
            LocalLlmSamplingPolicy.TEMPERATURE_ENV to "0",
            LocalLlmSamplingPolicy.TOP_K_ENV to "1",
            dev.clickn.translate.llm.LocalLlmAccelerationPolicy.VULKAN_OFFLOAD_ENV to "0",
        )
        val previous = environment.keys.associateWith(System::getenv)
        val rows = JSONArray()
        var engine: InferenceEngine? = null
        try {
            environment.forEach { (key, value) -> Os.setenv(key, value, true) }
            val active = AiChat.getInferenceEngine(runner.targetContext)
            engine = active
            active.loadModel(model.absolutePath)
            for (i in 0 until inputs.length()) {
                val source = inputs.getString(i)
                val prompt = HyMt2PromptPolicy.build(source, "ru", RuntimeTranslationPromptContext())
                val output = requireNotNull(LlamaMultiSequence.generateWithMetrics(listOf(prompt), listOf(128)))
                    .outputs.single().trim()
                assertTrue(output.any { it in 'А'..'я' || it == 'ё' })
                rows.put(JSONObject().put("source", source).put("translation", output))
            }
        } finally {
            try { engine?.destroy() } finally {
                previous.forEach { (key, value) -> if (value == null) Os.unsetenv(key) else Os.setenv(key, value, true) }
                File(root, "greedy.json").writeText(rows.toString(2))
            }
        }
    }
}
