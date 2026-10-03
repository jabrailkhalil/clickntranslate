// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.os.SystemClock
import dev.clickn.translate.util.CpuThreadPolicy
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import timber.log.Timber

/**
 * Optional debug-only adapter for a locally installed speech-bubble segmentation ONNX model.
 *
 * The model is intentionally not bundled or downloaded by the app. Evaluation builds can place a
 * compatible model at [modelFile]. If it is absent, the existing heuristic debug artifacts remain
 * unchanged and no inference work is performed.
 */
internal object MangaBubbleSegmentationDebugEngine {

    data class Output(
        val mask: BooleanArray,
        val detections: List<BubbleSegmentationPostprocessor.Detection>,
        val instanceMasks: List<BubbleSegmentationPostprocessor.InstanceMask>,
        val sessionPrepareMs: Long,
        val preprocessMs: Long,
        val inputTensorMs: Long,
        val inferenceMs: Long,
        val outputReadMs: Long,
        val postprocessMs: Long,
        val totalMs: Long,
    )

    private val inferenceLock = Mutex()
    private var session: OrtSession? = null
    private var pinnedOutputs: PinnedOutputs? = null
    private var loadedModelStamp: Pair<String, Long>? = null

    fun modelFile(context: Context): File =
        File(context.filesDir, "models/bubble_segmentation/$MODEL_FILE_NAME")

    fun isInstalled(context: Context): Boolean {
        val model = modelFile(context)
        return model.isFile && model.length() >= MIN_MODEL_BYTES
    }

    suspend fun runIfInstalled(context: Context, bitmap: Bitmap): Output? {
        if (!isInstalled(context)) return null
        val model = modelFile(context)
        return inferenceLock.withLock {
            withContext(Dispatchers.Default) {
                runInference(model, bitmap)
            }
        }
    }

    private fun runInference(model: File, bitmap: Bitmap): Output {
        val totalStartedAt = SystemClock.elapsedRealtime()
        val sessionStartedAt = SystemClock.elapsedRealtime()
        val activeSession = ensureSession(model)
        val sessionPrepareMs = SystemClock.elapsedRealtime() - sessionStartedAt
        val letterbox = BubbleSegmentationPostprocessor.Letterbox.create(
            sourceWidth = bitmap.width,
            sourceHeight = bitmap.height,
            inputSize = INPUT_SIZE,
        )
        val environment = OrtEnvironment.getEnvironment()
        val io = ensurePinnedOutputs(environment)

        val preprocessStartedAt = SystemClock.elapsedRealtime()
        bitmapToLetterboxedNchw(
            bitmap = bitmap,
            letterbox = letterbox,
            output = io.inputBuffer,
        )
        val preprocessMs = SystemClock.elapsedRealtime() - preprocessStartedAt
        val inputTensorMs = 0L

        val inferenceStartedAt = SystemClock.elapsedRealtime()
        val result = activeSession.run(
            io.inputMap(),
            io.outputMap(),
        )
        val inferenceMs = SystemClock.elapsedRealtime() - inferenceStartedAt
        result.use {
            val outputReadStartedAt = SystemClock.elapsedRealtime()
            val detectionOutput = io.detectionBuffer.toFloatArray()
            val prototypeOutput = io.prototypeBuffer.toFloatArray()
            val outputReadMs = SystemClock.elapsedRealtime() - outputReadStartedAt
            val postprocessStartedAt = SystemClock.elapsedRealtime()
            val processed = BubbleSegmentationPostprocessor.process(
                detectionOutput = detectionOutput,
                anchorCount = ANCHOR_COUNT,
                prototypeOutput = prototypeOutput,
                prototypeWidth = PROTOTYPE_WIDTH,
                prototypeHeight = PROTOTYPE_HEIGHT,
                maskChannelCount = MASK_CHANNEL_COUNT,
                letterbox = letterbox,
            )
            val postprocessMs = SystemClock.elapsedRealtime() - postprocessStartedAt
            return Output(
                mask = processed.unionMask,
                detections = processed.detections,
                instanceMasks = processed.instanceMasks,
                sessionPrepareMs = sessionPrepareMs,
                preprocessMs = preprocessMs,
                inputTensorMs = inputTensorMs,
                inferenceMs = inferenceMs,
                outputReadMs = outputReadMs,
                postprocessMs = postprocessMs,
                totalMs = SystemClock.elapsedRealtime() - totalStartedAt,
            )
        }
    }

    private fun ensureSession(model: File): OrtSession {
        val stamp = model.absolutePath to model.lastModified()
        session?.takeIf { loadedModelStamp == stamp }?.let { return it }
        runCatching { pinnedOutputs?.close() }
        pinnedOutputs = null
        runCatching { session?.close() }
        session = null
        loadedModelStamp = null

        val processors = CpuThreadPolicy.availableProcessors()
        val threads = CpuThreadPolicy.select(processors)
        val options = OrtSession.SessionOptions().apply {
            setIntraOpNumThreads(threads)
            setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
        }
        return try {
            OrtEnvironment.getEnvironment().createSession(model.absolutePath, options).also {
                session = it
                loadedModelStamp = stamp
                Timber.i(
                    "Manga bubble segmentation debug model ready: bytes=%d processors=%d ortThreads=%d",
                    model.length(),
                    processors,
                    threads,
                )
            }
        } finally {
            options.close()
        }
    }

    private fun ensurePinnedOutputs(environment: OrtEnvironment): PinnedOutputs {
        pinnedOutputs?.let { return it }
        return PinnedOutputs.create(environment).also { pinnedOutputs = it }
    }

    private fun bitmapToLetterboxedNchw(
        bitmap: Bitmap,
        letterbox: BubbleSegmentationPostprocessor.Letterbox,
        output: FloatBuffer,
    ) {
        require(output.capacity() == INPUT_FLOATS)
        val scaled = if (
            bitmap.width == letterbox.scaledWidth &&
            bitmap.height == letterbox.scaledHeight
        ) {
            bitmap
        } else {
            Bitmap.createScaledBitmap(
                bitmap,
                letterbox.scaledWidth,
                letterbox.scaledHeight,
                true,
            )
        }
        try {
            val scaledPixels = IntArray(letterbox.scaledWidth * letterbox.scaledHeight)
            scaled.getPixels(
                scaledPixels,
                0,
                letterbox.scaledWidth,
                0,
                0,
                letterbox.scaledWidth,
                letterbox.scaledHeight,
            )
            val planeSize = INPUT_SIZE * INPUT_SIZE
            val background = LETTERBOX_COLOR / 255f
            for (index in 0 until output.capacity()) {
                output.put(index, background)
            }
            for (y in 0 until letterbox.scaledHeight) {
                val outputRow = (y + letterbox.padTop) * INPUT_SIZE + letterbox.padLeft
                val sourceRow = y * letterbox.scaledWidth
                for (x in 0 until letterbox.scaledWidth) {
                    val pixel = scaledPixels[sourceRow + x]
                    val target = outputRow + x
                    output.put(target, ((pixel shr 16) and 0xFF) / 255f)
                    output.put(planeSize + target, ((pixel shr 8) and 0xFF) / 255f)
                    output.put(2 * planeSize + target, (pixel and 0xFF) / 255f)
                }
            }
            output.rewind()
        } finally {
            if (scaled !== bitmap) scaled.recycle()
        }
    }

    private fun FloatBuffer.toFloatArray(): FloatArray {
        val copy = duplicate()
        copy.rewind()
        return FloatArray(copy.remaining()).also(copy::get)
    }

    private class PinnedOutputs(
        val inputBuffer: FloatBuffer,
        val detectionBuffer: FloatBuffer,
        val prototypeBuffer: FloatBuffer,
        private val inputTensor: OnnxTensor,
        private val detectionTensor: OnnxTensor,
        private val prototypeTensor: OnnxTensor,
    ) : AutoCloseable {
        fun inputMap(): Map<String, OnnxTensor> = mapOf(
            INPUT_NAME to inputTensor,
        )

        fun outputMap(): Map<String, OnnxTensor> = mapOf(
            DETECTION_OUTPUT_NAME to detectionTensor,
            PROTOTYPE_OUTPUT_NAME to prototypeTensor,
        )

        override fun close() {
            runCatching { prototypeTensor.close() }
            runCatching { detectionTensor.close() }
            runCatching { inputTensor.close() }
        }

        companion object {
            fun create(environment: OrtEnvironment): PinnedOutputs {
                val inputBuffer = allocateFloatBuffer(INPUT_FLOATS)
                val detectionBuffer = allocateFloatBuffer(DETECTION_OUTPUT_FLOATS)
                val prototypeBuffer = allocateFloatBuffer(PROTOTYPE_OUTPUT_FLOATS)
                val inputTensor = OnnxTensor.createTensor(
                    environment,
                    inputBuffer,
                    longArrayOf(1, 3, INPUT_SIZE.toLong(), INPUT_SIZE.toLong()),
                )
                val detectionTensor = OnnxTensor.createTensor(
                    environment,
                    detectionBuffer,
                    longArrayOf(1, DETECTION_CHANNEL_COUNT.toLong(), ANCHOR_COUNT.toLong()),
                )
                val prototypeTensor = OnnxTensor.createTensor(
                    environment,
                    prototypeBuffer,
                    longArrayOf(
                        1,
                        MASK_CHANNEL_COUNT.toLong(),
                        PROTOTYPE_HEIGHT.toLong(),
                        PROTOTYPE_WIDTH.toLong(),
                    ),
                )
                return PinnedOutputs(
                    inputBuffer = inputBuffer,
                    detectionBuffer = detectionBuffer,
                    prototypeBuffer = prototypeBuffer,
                    inputTensor = inputTensor,
                    detectionTensor = detectionTensor,
                    prototypeTensor = prototypeTensor,
                )
            }

            private fun allocateFloatBuffer(floatCount: Int): FloatBuffer =
                ByteBuffer.allocateDirect(floatCount * Float.SIZE_BYTES)
                    .order(ByteOrder.nativeOrder())
                    .asFloatBuffer()
        }
    }

    const val MODEL_FILE_NAME = "best.onnx"
    private const val MIN_MODEL_BYTES = 1024L * 1024L
    private const val INPUT_NAME = "images"
    private const val DETECTION_OUTPUT_NAME = "output0"
    private const val PROTOTYPE_OUTPUT_NAME = "output1"
    private const val INPUT_SIZE = 640
    private const val INPUT_FLOATS = 3 * INPUT_SIZE * INPUT_SIZE
    private const val ANCHOR_COUNT = 8400
    private const val MASK_CHANNEL_COUNT = 32
    private const val DETECTION_CHANNEL_COUNT = 4 + 1 + MASK_CHANNEL_COUNT
    private const val PROTOTYPE_WIDTH = 160
    private const val PROTOTYPE_HEIGHT = 160
    private const val DETECTION_OUTPUT_FLOATS = DETECTION_CHANNEL_COUNT * ANCHOR_COUNT
    private const val PROTOTYPE_OUTPUT_FLOATS =
        MASK_CHANNEL_COUNT * PROTOTYPE_WIDTH * PROTOTYPE_HEIGHT
    private const val LETTERBOX_COLOR = 114
}
