// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import dev.clickn.translate.data.TranslatorEngine
import org.junit.Assert.assertEquals
import org.junit.Test

class TranslationPromptContextPolicyTest {
    @Test
    fun strategyFor_tableDriven_coversEveryTranslatorEngine() {
        val expected = mapOf(
            TranslatorEngine.OPENAI to TranslationPromptContextStrategy.GENERIC_STRUCTURED,
            TranslatorEngine.ANTHROPIC to TranslationPromptContextStrategy.GENERIC_STRUCTURED,
            TranslatorEngine.LOCAL_HY_MT2 to TranslationPromptContextStrategy.HY_MT2_OFFICIAL,
            TranslatorEngine.LOCAL_SAKURA to TranslationPromptContextStrategy.SAKURA_OFFICIAL,
            TranslatorEngine.DEEPL to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.NIUTRANS to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.YOUDAO_PICTRANS to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.LINGVA to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.MYMEMORY to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.LIBRETRANSLATE to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.GOOGLE to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.GOOGLE_ML_KIT to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.VOLC to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.BAIDU_FANYI to TranslationPromptContextStrategy.NONE,
            TranslatorEngine.TENCENT to TranslationPromptContextStrategy.NONE,
        )

        TranslatorEngine.values().forEach { engine ->
            assertEquals(engine.name, expected.getValue(engine), TranslationPromptContextPolicy.strategyFor(engine))
        }
    }
}
