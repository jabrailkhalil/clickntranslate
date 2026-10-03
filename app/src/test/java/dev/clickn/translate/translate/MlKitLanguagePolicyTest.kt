// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MlKitLanguagePolicyTest {
    @Test
    fun supportedLanguages_matchMlKitPublishedList() {
        val expected = setOf(
            "af", "ar", "be", "bg", "bn", "ca", "cs", "cy", "da", "de", "el", "en",
            "eo", "es", "et", "fa", "fi", "fr", "ga", "gl", "gu", "he", "hi", "hr",
            "ht", "hu", "id", "is", "it", "ja", "ka", "kn", "ko", "lt", "lv", "mk",
            "mr", "ms", "mt", "nl", "no", "pl", "pt", "ro", "ru", "sk", "sl", "sq",
            "sv", "sw", "ta", "te", "th", "tl", "tr", "uk", "ur", "vi", "zh",
        )

        assertEquals(expected, MlKitLanguagePolicy.supportedLanguageTags)
    }

    @Test
    fun configuredSourceAndTarget_tableDrivenNormalization() {
        data class Case(
            val name: String,
            val input: String,
            val expected: String,
        )

        val cases = listOf(
            Case("plain English", "en", "en"),
            Case("regional English", " en-US ", "en"),
            Case("simplified Chinese", "zh-CN", "zh"),
            Case("traditional Chinese", "zh_Hant", "zh"),
            Case("Norwegian Bokmal alias", "nb", "no"),
            Case("Filipino alias", "fil", "tl"),
            Case("legacy Hebrew alias", "iw", "he"),
            Case("regional Portuguese", "pt-BR", "pt"),
        )

        cases.forEach { case ->
            assertEquals(
                "${case.name} source",
                case.expected,
                MlKitLanguagePolicy.resolveConfiguredSource(case.input),
            )
            assertEquals(
                "${case.name} target",
                case.expected,
                MlKitLanguagePolicy.resolveTarget(case.input),
            )
        }
    }

    @Test
    fun invalidLanguageCases_tableDrivenErrors() {
        data class Case(
            val name: String,
            val action: () -> Any?,
            val messagePart: String?,
        )

        val cases = listOf(
            Case("auto source is silent", { MlKitLanguagePolicy.resolveConfiguredSource("auto") }, null),
            Case("blank source is silent", { MlKitLanguagePolicy.resolveConfiguredSource(" ") }, null),
            Case("auto target", { MlKitLanguagePolicy.resolveTarget("auto") }, "requires an explicit target language"),
            Case("blank target", { MlKitLanguagePolicy.resolveTarget(" ") }, "requires an explicit target language"),
            Case("unsupported source", { MlKitLanguagePolicy.resolveConfiguredSource("yue") }, "does not support the source language"),
            Case("unsupported target", { MlKitLanguagePolicy.resolveTarget("zu") }, "does not support the target language"),
        )

        cases.forEach { case ->
            val error = runCatching(case.action).exceptionOrNull()
            assertTrue("${case.name}: $error", error is TranslationException)
            if (case.messagePart == null) {
                assertTrue("${case.name}: ${error?.message}", error?.message.isNullOrEmpty())
            } else {
                assertTrue(
                    "${case.name}: ${error?.message}",
                    error?.message.orEmpty().contains(case.messagePart),
                )
            }
        }
    }

    @Test
    fun supportCheck_rejectsLanguagesOutsidePublishedList() {
        val supported = listOf("en", "en-US", "zh-CN", "zh-TW", "nb", "fil", "iw")
        val unsupported = listOf("auto", "", "yue", "zu", "az", "hy", "bs")

        supported.forEach { languageTag ->
            assertTrue(languageTag, MlKitLanguagePolicy.isSupportedLanguageTag(languageTag))
        }
        unsupported.forEach { languageTag ->
            assertTrue(languageTag, !MlKitLanguagePolicy.isSupportedLanguageTag(languageTag))
        }
    }
}
