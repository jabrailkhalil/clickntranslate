// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.glossary

import dev.clickn.translate.data.TranslatorEngine
import org.junit.Assert.assertEquals
import org.junit.Test

class TranslationPromptContextCapabilityTest {
    @Test
    fun promptContextSupport_coversEveryTranslatorEngine() {
        data class Case(val engine: TranslatorEngine, val expected: Boolean)

        val cases = listOf(
            Case(TranslatorEngine.OPENAI, true),
            Case(TranslatorEngine.ANTHROPIC, true),
            Case(TranslatorEngine.LOCAL_SAKURA, true),
            Case(TranslatorEngine.LOCAL_HY_MT2, true),
            Case(TranslatorEngine.DEEPL, false),
            Case(TranslatorEngine.YOUDAO_PICTRANS, false),
            Case(TranslatorEngine.GOOGLE, false),
            Case(TranslatorEngine.NIUTRANS, false),
            Case(TranslatorEngine.LINGVA, false),
            Case(TranslatorEngine.MYMEMORY, false),
            Case(TranslatorEngine.LIBRETRANSLATE, false),
            Case(TranslatorEngine.GOOGLE_ML_KIT, false),
            Case(TranslatorEngine.VOLC, false),
            Case(TranslatorEngine.BAIDU_FANYI, false),
            Case(TranslatorEngine.TENCENT, false),
        )

        assertEquals(TranslatorEngine.entries.toSet(), cases.map(Case::engine).toSet())
        cases.forEach { case ->
            assertEquals(case.engine.name, case.expected, supportsTranslationPromptContext(case.engine))
        }
    }
}
