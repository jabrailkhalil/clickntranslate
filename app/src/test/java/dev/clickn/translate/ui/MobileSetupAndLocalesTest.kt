package dev.clickn.translate.ui

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.*
import org.junit.Test

class MobileSetupAndLocalesTest {
    @Test fun screenSetupRequiresOverlayButOtherStepsRemainAvailable() {
        for (step in 0..6) {
            assertTrue(setupCanContinue(step, true))
            assertEquals(step != 2, setupCanContinue(step, false))
        }
    }

    @Test fun guidedLanguageSelectionRequiresASourceForServicesWithoutDetection() {
        for (engine in listOf(dev.clickn.translate.data.TranslatorEngine.MYMEMORY, dev.clickn.translate.data.TranslatorEngine.GOOGLE_ML_KIT)) {
            assertFalse(setupLanguagePairReady(dev.clickn.translate.data.Settings(translatorEngine = engine)))
            assertTrue(setupLanguagePairReady(dev.clickn.translate.data.Settings(translatorEngine = engine, sourceLang = "en")))
        }
        assertTrue(setupLanguagePairReady(dev.clickn.translate.data.Settings(translatorEngine = dev.clickn.translate.data.TranslatorEngine.GOOGLE)))
        assertFalse(setupLanguagePairReady(null))
    }

    @Test fun guidedSettingsLinksResolveToExistingSections() {
        for ((section, index) in listOf("ocr" to 4, "translate" to 2, "floating" to 10))
            assertEquals(section, index, settingsSectionIndex(section))
    }

    @Test fun allSixInterfaceLanguagesHaveEveryTranslatedStringAndMatchingFormatArguments() {
        val base = resources("values")
        val placeholder = Regex("%(?:\\d+\\$)?[-+# 0,(]*\\d*(?:\\.\\d+)?[a-zA-Z%]")
        for (locale in listOf("values-ru", "values-de", "values-fr", "values-es", "values-zh-rCN")) {
            val strings = resources(locale)
            base.forEach { (key, value) ->
                assertTrue("$locale missing $key", strings[key].orEmpty().isNotBlank())
                val expected = placeholder.findAll(value).map { it.value }.toList().sorted()
                val actual = placeholder.findAll(strings.getValue(key)).map { it.value }.toList().sorted()
                assertEquals("$locale/$key", expected, actual)
            }
        }
    }

    private fun resources(directory: String): Map<String, String> = buildMap {
        val folder = File("src/main/res/$directory")
        for (file in folder.listFiles().orEmpty().filter { it.extension == "xml" }) {
            val nodes = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file).getElementsByTagName("string")
            for (index in 0 until nodes.length) {
                val node = nodes.item(index)
                if (node.attributes.getNamedItem("translatable")?.nodeValue == "false") continue
                val name = node.attributes.getNamedItem("name").nodeValue
                assertFalse("duplicate $directory/$name", containsKey(name))
                put(name, node.textContent)
            }
        }
    }
}
