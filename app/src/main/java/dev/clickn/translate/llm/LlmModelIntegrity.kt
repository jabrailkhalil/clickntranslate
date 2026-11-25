package dev.clickn.translate.llm

import java.io.File
import java.security.MessageDigest

/** Runs only during explicit transfer validation, never during model-status polling. */
internal object LlmModelIntegrity {
    fun validate(
        file: File,
        expectedSizeBytes: Long,
        expectedSha256: String,
        checkpoint: () -> Unit = {},
    ): String? {
        require(expectedSizeBytes > 0 && expectedSha256.matches(Regex("[0-9a-f]{64}")))
        checkpoint()
        if (!file.isFile) return "missing"
        if (file.length() != expectedSizeBytes) return "pinned model size mismatch"
        val digest = MessageDigest.getInstance("SHA-256")
        var copied = 0L
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                checkpoint()
                val count = input.read(buffer)
                checkpoint()
                if (count < 0) break
                copied += count
                if (copied > expectedSizeBytes) return "pinned model size changed"
                digest.update(buffer, 0, count)
            }
        }
        checkpoint()
        if (copied != expectedSizeBytes) return "pinned model size changed"
        val actual = digest.digest().joinToString("") { "%02x".format(it) }
        return if (actual == expectedSha256) null else "pinned model SHA-256 mismatch"
    }
}
