// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

/** Request-scoped prompt data. It is deliberately excluded from persisted settings. */
data class RuntimeTranslationPromptContext(
    val currentApplication: String? = null,
    val glossary: List<RuntimeGlossaryTerm> = emptyList(),
    val currentPage: List<String> = emptyList(),
    val previousFrame: List<RuntimeDialogueTurn> = emptyList(),
)

data class RuntimeGlossaryTerm(
    val source: String,
    val target: String,
)

data class RuntimeDialogueTurn(
    val source: String,
    val translation: String? = null,
)
