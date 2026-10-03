// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import dev.clickn.translate.data.TranslatorEngine

/** Defines which prompt contract owns request-scoped translation context for each engine. */
internal enum class TranslationPromptContextStrategy {
    GENERIC_STRUCTURED,
    HY_MT2_OFFICIAL,
    SAKURA_OFFICIAL,
    NONE,
}

internal object TranslationPromptContextPolicy {
    fun strategyFor(engine: TranslatorEngine): TranslationPromptContextStrategy = when (engine) {
        TranslatorEngine.OPENAI,
        TranslatorEngine.ANTHROPIC -> TranslationPromptContextStrategy.GENERIC_STRUCTURED
        TranslatorEngine.LOCAL_HY_MT2 -> TranslationPromptContextStrategy.HY_MT2_OFFICIAL
        TranslatorEngine.LOCAL_SAKURA -> TranslationPromptContextStrategy.SAKURA_OFFICIAL
        TranslatorEngine.DEEPL,
        TranslatorEngine.NIUTRANS,
        TranslatorEngine.YOUDAO_PICTRANS,
        TranslatorEngine.GOOGLE,
        TranslatorEngine.LINGVA,
        TranslatorEngine.MYMEMORY,
        TranslatorEngine.LIBRETRANSLATE,
        TranslatorEngine.GOOGLE_ML_KIT,
        TranslatorEngine.VOLC,
        TranslatorEngine.BAIDU_FANYI,
        TranslatorEngine.TENCENT -> TranslationPromptContextStrategy.NONE
    }

    fun supportsContext(engine: TranslatorEngine): Boolean =
        strategyFor(engine) != TranslationPromptContextStrategy.NONE

    fun usesGenericRuntimeText(engine: TranslatorEngine): Boolean =
        strategyFor(engine) == TranslationPromptContextStrategy.GENERIC_STRUCTURED
}
