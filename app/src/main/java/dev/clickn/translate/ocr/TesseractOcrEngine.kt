package dev.clickn.translate.ocr

import android.graphics.Bitmap
import android.graphics.Rect
import com.googlecode.tesseract.android.TessBaseAPI
import dev.clickn.translate.data.OcrEngineKind
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Offline ara+eng. No network/model download is reachable from recognize(). */
@Singleton
class TesseractOcrEngine @Inject constructor(private val models: TesseractModelStore) : OcrEngine {
    private val mutex = Mutex()
    private val lifecycle = Any()
    private var closed = false
    private var active: TesseractRecognitionOwner? = null
    internal val recognizing: Boolean get() = synchronized(lifecycle) { active?.active == true }
    internal val nativeProgressSeen: Boolean get() = synchronized(lifecycle) { active?.progressSeen == true }

    override suspend fun recognize(bitmap: Bitmap, kind: OcrEngineKind): List<TextBlock> = mutex.withLock {
        require(kind == OcrEngineKind.TESSERACT_ARABIC)
        ensureOpen()
        models.withOcrModels { path -> coroutineScope {
            val stopper = launch(Dispatchers.Default, start = CoroutineStart.UNDISPATCHED) {
                try { awaitCancellation() } finally { synchronized(lifecycle) { active?.cancel() } }
            }
            try {
                withContext(Dispatchers.Default) { recognizeOwned(bitmap, path) }
            } finally {
                // withContext cannot finish until native recognition and its worker finally drain.
                withContext(NonCancellable) { stopper.cancelAndJoin() }
            }
        } }
    }

    private suspend fun recognizeOwned(bitmap: Bitmap, path: String): List<TextBlock> {
        currentCoroutineContext().ensureActive()
        ensureOpen()
        require(!bitmap.isRecycled && bitmap.width >= 8 && bitmap.height >= 8 && bitmap.width.toLong() * bitmap.height <= 24_000_000L)
        // This private immutable copy stays owned until native work drains, including cancellation.
        val image = requireNotNull(bitmap.copy(Bitmap.Config.ARGB_8888, false))
        var owner: TesseractRecognitionOwner? = null
        var api: TessBaseAPI? = null
        try {
            currentCoroutineContext().ensureActive()
            val native = TessBaseAPI { owner?.progress() }
            api = native
            val lease = TesseractRecognitionOwner { native.stop() }
            owner = lease
            synchronized(lifecycle) {
                if (closed) throw CancellationException("Arabic OCR closed")
                active = lease
            }
            if (!native.init(path, "ara+eng", TessBaseAPI.OEM_LSTM_ONLY)) throw TesseractModelException(TesseractModelFailure.INVALID)
            currentCoroutineContext().ensureActive(); lease.ensureActive()
            native.pageSegMode = TessBaseAPI.PageSegMode.PSM_AUTO
            native.setImage(image)
            currentCoroutineContext().ensureActive(); lease.begin()
            // Only hOCR recognition supports TessBaseAPI.stop(); UTF8Text alone does not.
            native.getHOCRText(0)
            currentCoroutineContext().ensureActive(); lease.ensureActive(); ensureOpen()
            return paragraphs(native, image.width, image.height).also {
                currentCoroutineContext().ensureActive(); lease.ensureActive(); ensureOpen()
            }
        } finally {
            synchronized(lifecycle) { if (active === owner) active = null }
            val releaseOwner = owner
            try { if (releaseOwner != null) releaseOwner.dispose { api?.recycle() } else api?.recycle() }
            finally { image.recycle() }
        }
    }

    private suspend fun paragraphs(api: TessBaseAPI, width: Int, height: Int): List<TextBlock> {
        val iterator = api.resultIterator ?: return emptyList()
        val output = mutableListOf<TextBlock>()
        var text = ""
        var bounds: Rect? = null
        var confidence = 0f
        var sources = mutableListOf<Rect>()
        var paragraphId = -1
        var totalLength = 0L
        fun finish() {
            val box = bounds
            if (text.isBlank() || box == null) return
            totalLength += text.length
            check(output.size < 2_000 && totalLength <= 100_000L) { "Arabic OCR result is too large" }
            output += TextBlock(text, box, confidence,
                recognizedLanguage = TesseractTextPolicy.language(text),
                layoutOrientation = if (TesseractTextPolicy.rtl(text)) TextOrientation.HORIZONTAL_RTL else TextOrientation.HORIZONTAL_LTR,
                sourceBoxes = sources.toList().ifEmpty { listOf(Rect(box)) },
                regionId = paragraphId, parentRegionId = paragraphId, regionGranularity = TextRegionGranularity.PARAGRAPH)
        }
        try {
            iterator.begin()
            do {
                currentCoroutineContext().ensureActive()
                // ResultIterator's beginning predicate also checks logical symbol position (BiDi).
                // Always consume the initial paragraph and track its native container across lines.
                val paragraphBounds = checked(iterator.getBoundingRect(TessBaseAPI.PageIteratorLevel.RIL_PARA), width, height)
                if (paragraphId < 0 || paragraphBounds != bounds ||
                    iterator.isAtBeginningOf(TessBaseAPI.PageIteratorLevel.RIL_PARA)) {
                    finish(); paragraphId++
                    text = iterator.getUTF8Text(TessBaseAPI.PageIteratorLevel.RIL_PARA).orEmpty().trim()
                    bounds = paragraphBounds
                    confidence = iterator.confidence(TessBaseAPI.PageIteratorLevel.RIL_PARA).let { if (it.isFinite()) (it / 100f).coerceIn(0f, 1f) else 0f }
                    sources = mutableListOf()
                }
                checked(iterator.getBoundingRect(TessBaseAPI.PageIteratorLevel.RIL_TEXTLINE), width, height)?.let { sources += it }
                check(text.length <= 100_000 && sources.size <= 10_000) { "Arabic OCR paragraph is too large" }
            } while (iterator.next(TessBaseAPI.PageIteratorLevel.RIL_TEXTLINE))
            finish()
        } finally { iterator.delete() }
        return output
    }

    private fun checked(rect: Rect, width: Int, height: Int): Rect? = Rect(rect.left.coerceIn(0, width), rect.top.coerceIn(0, height),
        rect.right.coerceIn(0, width), rect.bottom.coerceIn(0, height)).takeIf { !it.isEmpty }

    private fun ensureOpen() = synchronized(lifecycle) { if (closed) throw CancellationException("Arabic OCR closed") }
    override fun close() { synchronized(lifecycle) { closed = true; active?.cancel() } }
}
