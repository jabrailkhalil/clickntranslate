package dev.clickn.translate.ocr

import java.io.File
import java.io.InterruptedIOException
import java.nio.file.Files
import java.security.MessageDigest

internal data class TesseractModelSpec(val language: String, val bytes: Long, val sha256: String, val url: String)

/** Independently pinned best Arabic and fast English. No branch URL/checksum is trusted. */
internal object TesseractModelFiles {
    const val ARABIC_REVISION = "e12c65a915945e4c28e237a9b52bc4a8f39a0cec"
    const val ENGLISH_REVISION = "65727574dfcd264acbb0c3e07860e4e9e9b22185"
    // A new verified directory leaves previously installed profiles intact.
    const val REVISION = "ara-best-e12c65a91594_eng-fast-65727574dfcd"
    val models = listOf(
        spec("ara", 12_603_724L, "ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896", "tessdata_best", ARABIC_REVISION),
        spec("eng", 4_113_088L, "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2", "tessdata_fast", ENGLISH_REVISION),
    )
    private fun spec(language: String, bytes: Long, sha256: String, repository: String, revision: String) = TesseractModelSpec(language, bytes, sha256,
        "https://raw.githubusercontent.com/tesseract-ocr/$repository/$revision/$language.traineddata")

    fun verified(file: File, spec: TesseractModelSpec): Boolean {
        if (!file.isFile || Files.isSymbolicLink(file.toPath()) || file.length() != spec.bytes) return false
        val hash = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(16_384)
            while (true) {
                if (Thread.currentThread().isInterrupted) throw InterruptedIOException("Model verification cancelled")
                val read = input.read(buffer)
                if (read < 0) break
                hash.update(buffer, 0, read)
            }
        }
        return hash.digest().joinToString("") { "%02x".format(it) } == spec.sha256
    }
}
