package dev.clickn.translate.data

import dev.clickn.translate.glossary.GlossaryImportFormatException
import dev.clickn.translate.glossary.decodeGlossaryImportUtf8
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.nio.charset.CharacterCodingException
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import org.junit.Assert.*
import org.junit.Test

class SettingsTransferEncodingTest {
    @Test fun malformedUtf8CannotBecomeReplacementCharactersInImportedUserData() {
        val invalid = "{\"targetLang\":\"".toByteArray() + byteArrayOf(0xC3.toByte(), 0x28) + "\"}".toByteArray()
        val zip = ByteArrayOutputStream().also { output ->
            ZipOutputStream(output).use { writer ->
                writer.putNextEntry(ZipEntry("manifest.json"))
                writer.write(invalid)
                writer.closeEntry()
            }
        }.toByteArray()
        assertTrue(runCatching { SettingsBundleTransfer.readPreview(ByteArrayInputStream(zip)) }.exceptionOrNull() is CharacterCodingException)
        assertTrue(runCatching { TranslationPresetTransfer.readUtf8Limited(ByteArrayInputStream(invalid)) }.exceptionOrNull() is CharacterCodingException)
        assertTrue(runCatching { decodeGlossaryImportUtf8(invalid) }.exceptionOrNull() is GlossaryImportFormatException)
    }

    @Test fun validBomArabicAndMixedTextAreReadWithoutChangingUserContent() {
        val text = "{\"term\":\"افتح Settings (الإعدادات) 😀\"}"
        val bytes = ("\uFEFF" + text).toByteArray(Charsets.UTF_8)
        assertEquals(text, TranslationPresetTransfer.readUtf8Limited(ByteArrayInputStream(bytes)))
        assertEquals("\uFEFF" + text, decodeGlossaryImportUtf8(bytes))
    }
}
