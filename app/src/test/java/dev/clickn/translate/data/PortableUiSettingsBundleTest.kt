package dev.clickn.translate.data

import dev.clickn.translate.ui.theme.ThemeMode
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream
import org.junit.Assert.*
import org.junit.Test

class PortableUiSettingsBundleTest {
    @Test fun v3RoundTripIncludesUiChoicesAndExcludesCredentials() {
        val ui = PortableUiPreferences(ThemeMode.AMOLED, "OCEAN", "ru", "doc")
        val output = ByteArrayOutputStream()
        SettingsBundleTransfer.write(output, Settings(apiKey = "private-fixture-secret"),
            uiPreferences = ui, resolveFontFile = { null })
        val preview = SettingsBundleTransfer.readPreview(output.toByteArray().inputStream())
        assertEquals(3, preview.formatVersion)
        assertEquals(ui, preview.uiPreferences)
        val manifest = ZipInputStream(output.toByteArray().inputStream()).use {
            it.nextEntry
            it.readBytes().toString(Charsets.UTF_8)
        }
        assertTrue(manifest.contains("\"minimumReaderVersion\":3"))
        assertFalse(manifest.contains("private-fixture-secret"))
        assertFalse(manifest.contains("keep_visible"))
        assertFalse(manifest.contains("portable_revision"))
    }

    @Test fun v1AndV2FilesDoNotInventUiChoices() {
        for ((version, settings) in listOf(1 to "{}", 2 to """{"values":{"targetLang":"de"}}""")) {
            val preview = SettingsBundleTransfer.readPreview(bundle(version, settings).inputStream())
            assertEquals(version, preview.formatVersion)
            assertNull(preview.uiPreferences)
            if (version == 2) assertEquals("de", preview.settings!!.targetLang)
        }
    }

    @Test fun systemLanguageAndAbsentCompanionArePortableWithoutConfirmingSetup() {
        val ui = PortableUiPreferences(themeMode = ThemeMode.FOLLOW_SYSTEM, languageTag = "")
        val output = ByteArrayOutputStream()
        SettingsBundleTransfer.write(output, Settings(), uiPreferences = ui) { null }
        assertEquals(ui, SettingsBundleTransfer.readPreview(output.toByteArray().inputStream()).uiPreferences)
    }

    @Test fun invalidInterfaceValuesRejectThePackage() {
        for (ui in listOf(
            """{"themeMode":99}""", """{"accent":"unknown"}""",
            """{"languageTag":"../locale"}""", """{"companion":"custom"}""",
        )) {
            val failure = runCatching {
                SettingsBundleTransfer.readPreview(bundle(3, """{"values":{}}""", ui).inputStream())
            }.exceptionOrNull()
            assertTrue("Invalid UI values must reject the package", failure is IllegalArgumentException)
        }
    }

    @Test fun invalidExportNeverTouchesTheDestination() {
        val output = ByteArrayOutputStream()
        assertTrue(runCatching {
            SettingsBundleTransfer.write(output, Settings(),
                uiPreferences = PortableUiPreferences(companion = "custom")) { null }
        }.isFailure)
        assertEquals(0, output.size())
    }

    @Test fun olderVersionCannotSmuggleNewUiChanges() {
        assertTrue(runCatching {
            SettingsBundleTransfer.readPreview(bundle(2, """{"values":{}}""",
                """{"themeMode":3}""").inputStream())
        }.isFailure)
    }

    @Test fun futurePackageVersionIsRejected() {
        val bytes = bundle(4, """{"values":{}}""")
        assertTrue(runCatching { SettingsBundleTransfer.readPreview(bytes.inputStream()) }.isFailure)
    }

    private fun bundle(version: Int, settings: String, ui: String? = null): ByteArray =
        ByteArrayOutputStream().also { output ->
            ZipOutputStream(output).use { zip ->
                zip.putNextEntry(ZipEntry("manifest.json"))
                val uiField = ui?.let { ",\"uiPreferences\":$it" }.orEmpty()
                zip.write("""{"format":"clickntranslate.settings","version":$version,"minimumReaderVersion":$version,"settings":$settings,"fonts":[]$uiField}""".toByteArray())
                zip.closeEntry()
            }
        }.toByteArray()
}
