// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TranslationLogElapsedCoverageTest {

    @Test
    fun translatePairLogs_includeElapsedTime() {
        data class Case(
            val path: String,
            val expectedPairCalls: Int,
        )

        val cases = listOf(
            Case("src/main/java/dev/clickn/translate/service/CaptureService.kt", expectedPairCalls = 6),
            Case("src/main/java/dev/clickn/translate/translate/ProcessTextTranslateActivity.kt", expectedPairCalls = 1),
        )

        cases.forEach { case ->
            val source = File(case.path).readText()
            val starts = translatePairCallStarts(source)
            assertEquals(case.path, case.expectedPairCalls, starts.size)
            starts.forEachIndexed { index, start ->
                val snippet = source.substring(start, (start + 260).coerceAtMost(source.length))
                assertTrue("${case.path} translate pair #${index + 1} is missing elapsedMs", "elapsedMs =" in snippet)
            }
        }
    }

    private fun translatePairCallStarts(source: String): List<Int> {
        val pattern = "logRepository.pair("
        val starts = mutableListOf<Int>()
        var index = source.indexOf(pattern)
        while (index >= 0) {
            val snippet = source.substring(index, (index + 160).coerceAtMost(source.length))
            if ("LogRepository.Category.TRANSLATE" in snippet) {
                starts += index
            }
            index = source.indexOf(pattern, index + pattern.length)
        }
        return starts
    }
}
