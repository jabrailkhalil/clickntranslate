package dev.clickn.translate.llm

import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest

/** Runs only during explicit transfer validation, never during model-status polling. */
internal object LlmModelIntegrity {
    data class Pin(val sizeBytes: Long, val sha256: String) {
        init {
            require(sizeBytes > 0 && sha256.matches(Regex("[0-9a-f]{64}")))
        }
    }

    fun importPin(kind: LlmModelKind, displayName: String): Pin? =
        if (displayName.equals(kind.fileName, ignoreCase = true)) Pin(kind.expectedSizeBytes, kind.expectedSha256)
        else null

    fun validate(
        file: File,
        expectedSizeBytes: Long,
        expectedSha256: String,
        checkpoint: () -> Unit = {},
    ): String? {
        val pin = Pin(expectedSizeBytes, expectedSha256)
        checkpoint()
        if (!file.isFile) return "missing"
        if (file.length() != expectedSizeBytes) return "pinned model size mismatch"
        return file.inputStream().use { copyAndVerify(it, null, pin, checkpoint) }
    }

    /** A manual import copies each byte once. Custom weights have no publisher pin. */
    fun copyAndVerify(input: InputStream, output: OutputStream?, pin: Pin?, checkpoint: () -> Unit): String? {
        val digest = pin?.let { MessageDigest.getInstance("SHA-256") }
        val buffer = ByteArray(64 * 1024)
        var copied = 0L
        while (true) {
            checkpoint()
            val count = input.read(buffer)
            checkpoint()
            if (count < 0) break
            copied += count
            if (pin != null && copied > pin.sizeBytes) return "pinned model size mismatch"
            output?.write(buffer, 0, count)
            digest?.update(buffer, 0, count)
        }
        checkpoint()
        if (pin == null) return null
        if (copied != pin.sizeBytes) return "pinned model size mismatch"
        val actual = checkNotNull(digest).digest().joinToString("") { "%02x".format(it) }
        return if (actual == pin.sha256) null else "pinned model SHA-256 mismatch"
    }
}
