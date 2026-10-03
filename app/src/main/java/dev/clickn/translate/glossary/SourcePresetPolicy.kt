package dev.clickn.translate.glossary

/** Bundled packs are opt-in runtime data, never hundreds of user database entries. */
internal object SourcePresetPolicy {
    fun isUntouchedLegacySeed(term: GlossaryTermEntity, sounds: Set<String>): Boolean =
        term.category == GlossaryTermCategory.PRESERVE_SOURCE &&
        term.scopePackage.isEmpty() && term.sourceLang == "ja" && term.targetLang == "*" &&
        term.sourceTerm in sounds && term.targetTerm == term.sourceTerm &&
        !term.caseSensitive && term.enabled && term.createdAtMs == term.updatedAtMs

    fun activeTerms(userTerms: List<GlossaryTermEntity>, sounds: Set<String>, includePack: Boolean): List<GlossaryTermEntity> {
        val own = userTerms.filter { it.category == GlossaryTermCategory.PRESERVE_SOURCE }
        if (!includePack) return own.filter(GlossaryTermEntity::enabled)
        val overrides = own.filter { it.scopePackage.isEmpty() && it.sourceLang == "ja" }
            .map { normalizeGlossaryTerm(it.sourceTerm, false) }.toSet()
        return own.filter(GlossaryTermEntity::enabled) + sounds.filterNot {
            normalizeGlossaryTerm(it, false) in overrides
        }.map { sound ->
            GlossaryTermEntity(sourceLang = "ja", targetLang = "*", sourceTerm = sound,
                targetTerm = sound, category = GlossaryTermCategory.PRESERVE_SOURCE)
        }
    }
}
