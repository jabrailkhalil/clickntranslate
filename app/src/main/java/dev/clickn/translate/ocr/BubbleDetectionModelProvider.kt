// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ocr

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import timber.log.Timber

/**
 * Publishes the Apache-2.0 RT-DETR-v2 comic bubble detector bundled inside the APK.
 *
 * ONNX Runtime opens models by filesystem path, so the verified asset is copied once to the app's
 * private no-backup directory. There is no user-visible download or delete lifecycle.
 */
internal object BubbleDetectionModelProvider {
    const val MODEL_FILE_NAME = "detector-v4-s_int8.onnx"
    const val BUNDLED_ASSET_PATH = "models/bubble_detection/$MODEL_FILE_NAME"
    const val MODEL_SOURCE_URL =
        "https://huggingface.co/ogkalu/comic-text-and-bubble-detector"
    const val MODEL_LICENSE = "Apache-2.0"
    const val EXPECTED_BYTES = 11_120_765L
    const val EXPECTED_SHA256 =
        "5FE9E4F576E49D4E7E8B0E029D6D3CDC252ABD4694113E1CAE120E62C931EA79"

    private const val PRIVATE_MODEL_DIRECTORY = "bundled_models/bubble_detection"
    private val lock = Any()
    private var readyStamp: Triple<String, Long, Long>? = null

    fun prepare(context: Context): File? = synchronized(lock) {
        val destination = File(
            context.noBackupFilesDir,
            "$PRIVATE_MODEL_DIRECTORY/$MODEL_FILE_NAME",
        )
        val stamp = destination.stamp()
        if (stamp != null && readyStamp == stamp) return@synchronized destination
        if (validateModelFile(destination) == null) {
            readyStamp = destination.stamp()
            return@synchronized destination
        }

        val directory = destination.parentFile ?: return@synchronized null
        val temporary = File(directory, "$MODEL_FILE_NAME.asset.tmp")
        try {
            directory.mkdirs()
            context.assets.open(BUNDLED_ASSET_PATH).use { input ->
                FileOutputStream(temporary).use(input::copyTo)
            }
            validateModelFile(temporary)?.let { reason ->
                error("invalid bundled bubble detector: $reason")
            }
            if (destination.exists() && !destination.delete()) {
                error("unable to replace ${destination.name}")
            }
            if (!temporary.renameTo(destination)) {
                error("unable to publish ${destination.name}")
            }
            readyStamp = destination.stamp()
            Timber.i(
                "Bundled bubble detector prepared bytes=%d sha256=%s",
                destination.length(),
                EXPECTED_SHA256,
            )
            destination
        } catch (error: Throwable) {
            readyStamp = null
            Timber.w(error, "Unable to prepare bundled bubble detector")
            null
        } finally {
            if (temporary.exists() && !temporary.delete()) {
                Timber.w("Unable to remove temporary bubble detector: %s", temporary)
            }
        }
    }

    internal fun validateModelFile(file: File): String? {
        if (!file.isFile) return "missing"
        if (file.length() != EXPECTED_BYTES) {
            return "size mismatch: ${file.length()} bytes"
        }
        val actual = runCatching { sha256(file) }
            .getOrElse { return "unreadable: ${it.message}" }
        return if (actual.equals(EXPECTED_SHA256, ignoreCase = true)) {
            null
        } else {
            "SHA-256 mismatch: $actual"
        }
    }

    private fun File.stamp(): Triple<String, Long, Long>? =
        takeIf(File::isFile)?.let { Triple(it.absolutePath, it.length(), it.lastModified()) }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count <= 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { byte -> "%02X".format(byte) }
    }
}
