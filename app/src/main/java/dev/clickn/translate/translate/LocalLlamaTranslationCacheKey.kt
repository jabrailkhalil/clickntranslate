// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.translate

import dev.clickn.translate.llm.LlmModelKind

internal object LocalLlamaTranslationCacheKey {

    fun build(
        cache: TranslationCache,
        source: String,
        modelKind: LlmModelKind,
        sourceLang: String,
        targetLang: String,
        maxNewTokens: Int,
        systemPrompt: String?,
        userPrompt: String,
    ): String = cache.key(
        source = source.trim(),
        model = modelKind.name,
        targetLang = targetLang.trim().lowercase(),
        prompt = promptFingerprint(
            sourceLang = sourceLang,
            targetLang = targetLang,
            maxNewTokens = maxNewTokens,
            systemPrompt = systemPrompt,
            userPrompt = userPrompt,
        )
    )

    internal fun promptFingerprint(
        sourceLang: String,
        targetLang: String,
        maxNewTokens: Int,
        systemPrompt: String?,
        userPrompt: String,
    ): String = buildString {
        append("sourceLang=")
        append(sourceLang.trim().lowercase())
        append("|targetLang=")
        append(targetLang.trim().lowercase())
        append("|maxNewTokens=")
        append(maxNewTokens)
        append("|system=")
        append(systemPrompt.orEmpty())
        append("|user=")
        append(userPrompt)
    }
}
