package dev.clickn.translate.glossary

import dev.clickn.translate.util.decodeStrictUtf8
import java.nio.charset.CharacterCodingException

/** A malformed file must fail before the preview or any database write, never create replacement terms. */
internal fun decodeGlossaryImportUtf8(bytes: ByteArray): String {
    if (bytes.size > GLOSSARY_IMPORT_MAX_FILE_BYTES) {
        throw GlossaryImportFormatException("Glossary file is too large.")
    }
    return try {
        decodeStrictUtf8(bytes)
    } catch (_: CharacterCodingException) {
        throw GlossaryImportFormatException("Glossary file must contain valid UTF-8.")
    }
}
