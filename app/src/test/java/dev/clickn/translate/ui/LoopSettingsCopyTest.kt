// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import java.io.File
import java.util.Locale
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LoopSettingsCopyTest {

    @Test
    fun loopOptionLabels_doNotMarkChoicesAsRecommended() {
        data class Case(
            val name: String,
            val resourcePath: String,
        )

        val cases = listOf(
            Case("English", "src/main/res/values/strings.xml"),
            Case("Simplified Chinese", "src/main/res/values-zh-rCN/strings.xml"),
            Case("Russian", "src/main/res/values-ru/strings.xml"),
            Case("German", "src/main/res/values-de/strings.xml"),
            Case("French", "src/main/res/values-fr/strings.xml"),
            Case("Spanish", "src/main/res/values-es/strings.xml"),
        )

        cases.forEach { case ->
            val resources = readStringResources(case.resourcePath)
            val modes = listOf("settings_loop_trigger_smart", "settings_loop_trigger_settled", "settings_loop_trigger_fixed")
                .map { resources[it].orEmpty().trim() }
            val labels = modes + resources["settings_loop_text_region_auto"].orEmpty().trim()
            assertTrue("${case.name}: every choice has a localized label", labels.all(String::isNotBlank))
            assertEquals("${case.name}: the three modes must be distinguishable", 3, modes.toSet().size)
            // Translation wording may improve; the UI must keep neutral choices in every locale.
            labels.forEach { label ->
                val lower = label.lowercase(Locale.ROOT)
                assertFalse("${case.name}: choice must not be marked recommended: $label",
                    listOf("recommend", "recomend", "recommand", "empfohlen", "рекоменду", "推荐").any(lower::contains))
            }
        }
    }

    private fun readStringResources(relativePath: String): Map<String, String> {
        val file = listOf(File(relativePath), File("app/$relativePath"))
            .firstOrNull(File::isFile) ?: error("Resource file not found: $relativePath")
        val document = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(file)
        val nodes = document.getElementsByTagName("string")
        return buildMap {
            for (index in 0 until nodes.length) {
                val node = nodes.item(index)
                val name = node.attributes?.getNamedItem("name")?.nodeValue ?: continue
                put(name, node.textContent)
            }
        }
    }
}
