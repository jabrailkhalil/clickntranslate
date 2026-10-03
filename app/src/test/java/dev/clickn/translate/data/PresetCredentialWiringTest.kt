// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.*
import org.junit.Test
import org.w3c.dom.Element

class PresetCredentialWiringTest {
    @Test
    fun everySwitchEntryUsesRepositoryAndSettingsSavePassesTheLiveForm() {
        listOf(
            "src/main/java/dev/clickn/translate/ui/SettingsViewModel.kt" to "repo.applyTranslationPreset(id)",
            "src/main/java/dev/clickn/translate/ui/MainScreen.kt" to "repo.applyTranslationPreset(id)",
            "src/main/java/dev/clickn/translate/ui/MainScreen.kt" to "repo.applyTranslationPreset(targetId, presetToSave)",
            "src/main/java/dev/clickn/translate/service/CaptureService.kt" to "settingsRepository.applyTranslationPreset(preset.id)",
            "src/main/java/dev/clickn/translate/ui/SettingsScreen.kt" to "saveTranslationPreset(preset, buildTranslationPresetSnapshot())",
            "src/main/java/dev/clickn/translate/gallery/GalleryTranslationRepository.kt" to "settingsRepository.settingsForSnapshot(snapshot)",
        ).forEach { (path, marker) -> assertTrue(path, file(path).readText().contains(marker)) }
    }

    @Test
    fun localCredentialRecordsStayOutsideTransferObjectsAndBackup_tableDriven() {
        listOf("Settings.kt", "TranslationPresetTransfer.kt", "SettingsBundleTransfer.kt").forEach { name ->
            val source = file("src/main/java/dev/clickn/translate/data/$name").readText()
            assertFalse(name, source.contains("PresetCredentialRecord"))
            assertFalse(name, source.contains("local_preset_credentials_v1_"))
        }
        listOf("backup_rules.xml" to 1, "data_extraction_rules.xml" to 2).forEach { (name, count) ->
            val root = DocumentBuilderFactory.newInstance().apply {
                setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)
            }.newDocumentBuilder().parse(file("src/main/res/xml/$name"))
            val nodes = root.getElementsByTagName("include")
            val inclusions = (0 until nodes.length).map { nodes.item(it) as Element }
            assertEquals(name, count, inclusions.size)
            inclusions.forEach {
                assertEquals(name, "sharedpref", it.getAttribute("domain"))
                assertEquals(name, ".", it.getAttribute("path"))
            }
            // An explicit include list excludes all other domains, including DataStore.
            val exclusions = root.getElementsByTagName("exclude")
            assertEquals(name, count, exclusions.length)
            (0 until exclusions.length).forEach { index ->
                val exclusion = exclusions.item(index) as Element
                assertEquals(name, "sharedpref", exclusion.getAttribute("domain"))
                assertEquals(name, "clickn_text_history.xml", exclusion.getAttribute("path"))
            }
        }
    }

    @Test
    fun keystoreFailureCannotWriteDeviceDerivedCiphertext() {
        val source = file("src/main/java/dev/clickn/translate/data/SettingsSecretCipher.kt").readText()
        val encryption = source.substringAfter("override fun encrypt(").substringBefore("override fun decrypt(")
        assertFalse(encryption.contains("fallbackKey"))
        assertFalse(encryption.contains("FALLBACK_PREFIX"))
        assertTrue(encryption.contains("getOrCreateKey()"))
        assertTrue("legacy ciphertext must remain readable", source.contains("decryptWithKey(fallbackKey"))
    }

    private fun file(path: String): File = listOf(File(path), File("app", path)).first(File::isFile)
}
