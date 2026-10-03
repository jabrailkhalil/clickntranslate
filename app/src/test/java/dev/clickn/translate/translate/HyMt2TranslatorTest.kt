// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import org.junit.Assert.assertEquals
import org.junit.Test

class HyMt2TranslatorTest {

    @Test
    fun normalizeTargetLang_defaultsBlankAndAutoToUsersLanguage() {
        data class Case(
            val targetLang: String,
            val expected: String,
        )

        val cases = listOf(
            Case("zh-CN", "zh-CN"),
            Case(" zh-TW ", "zh-TW"),
            Case("en", "en"),
            Case("auto", dev.clickn.translate.data.defaultTranslationTarget()),
            Case(" AUTO ", dev.clickn.translate.data.defaultTranslationTarget()),
            Case("", dev.clickn.translate.data.defaultTranslationTarget()),
            Case("   ", dev.clickn.translate.data.defaultTranslationTarget()),
        )

        cases.forEach { case ->
            assertEquals(
                case.toString(),
                case.expected,
                HyMt2Translator.normalizeTargetLang(case.targetLang)
            )
        }
    }
}
