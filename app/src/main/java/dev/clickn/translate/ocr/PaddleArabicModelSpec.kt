package dev.clickn.translate.ocr

import java.io.File
import java.io.InterruptedIOException
import java.security.MessageDigest

/** A pack file has the same identity through the official host, a mirror, or a local import. */
internal data class PaddlePinnedModelFile(
    val fileName: String,
    val repository: String,
    val revision: String,
    val sourceFileName: String,
    val bytes: Long,
    val sha256: String,
) {
    val urls: List<String> get() = listOf("https://huggingface.co", "https://hf-mirror.com").map { host ->
        "$host/$repository/resolve/$revision/$sourceFileName"
    }

    fun validationError(file: File): String? {
        if (!file.isFile || file.length() != bytes) return "pinned model size mismatch"
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(16_384)
            while (true) {
                if (Thread.currentThread().isInterrupted) throw InterruptedIOException("Model verification cancelled")
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        val actual = digest.digest().joinToString("") { "%02x".format(it) }
        return if (actual == sha256) null else "pinned model SHA-256 mismatch"
    }
}

/**
 * Official PaddlePaddle exports, Apache-2.0. No format conversion or extra runtime is required.
 * Recognition provenance and LFS hash:
 * https://huggingface.co/PaddlePaddle/arabic_PP-OCRv5_mobile_rec_onnx/commit/14aaedcd75825982689ecf5cd64ab33ee083215a
 * The exact UTF-8 inference.yml below contains 747 CTC keys; blank and space are decoder tokens.
 */
internal object PaddleArabicModelSpec {
    const val RECOGNITION_REVISION = "14aaedcd75825982689ecf5cd64ab33ee083215a"
    const val LICENSE = "Apache-2.0"

    val detection = PaddlePinnedModelFile(
        fileName = "det.onnx",
        repository = "PaddlePaddle/PP-OCRv5_mobile_det_onnx",
        revision = "e6f4fa85f00e168c862bc462aebca69eef9b3d3d",
        sourceFileName = "inference.onnx",
        bytes = 4_826_518L,
        sha256 = "a431985659dc921974177a95adcfbb90fd9e51989a5e04d70d0b75f597b6e61d",
    )
    val recognition = PaddlePinnedModelFile(
        fileName = "rec.onnx",
        repository = "PaddlePaddle/arabic_PP-OCRv5_mobile_rec_onnx",
        revision = RECOGNITION_REVISION,
        sourceFileName = "inference.onnx",
        bytes = 7_998_947L,
        sha256 = "799113ebf267fbe742deb99eb36e8d42c9ddc5291ceacf92add41b4d52a59110",
    )
    val keys = PaddlePinnedModelFile(
        fileName = "keys.yml",
        repository = "PaddlePaddle/arabic_PP-OCRv5_mobile_rec_onnx",
        revision = RECOGNITION_REVISION,
        sourceFileName = "inference.yml",
        bytes = 6_165L,
        sha256 = "21368419e6c016c31db55d316d59e11c128e1913e6e6fe10287084710043d3a6",
    )

    val files: List<PaddlePinnedModelFile> = listOf(detection, recognition, keys)
    fun forFile(name: String): PaddlePinnedModelFile? = files.firstOrNull { it.fileName == name }
}
