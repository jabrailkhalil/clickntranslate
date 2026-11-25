package dev.clickn.translate.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject

/** Memory-only field delta. Values may contain credentials; never persist or log this object. */
internal class SettingsEditorChanges private constructor(private val values: Map<String, JsonElement>) {
    val fieldNames: Set<String> get() = values.keys
    val isEmpty: Boolean get() = values.isEmpty()

    /** Explicit user edits win same-field conflicts; untouched fields always come from latest. */
    fun applyTo(latest: Settings, normalizedDraft: Settings? = null): Settings {
        if (values.isEmpty()) return latest
        val replacements = normalizedDraft?.let { json.encodeToJsonElement(it).jsonObject }
        val encoded = json.encodeToJsonElement(latest).jsonObject.toMutableMap()
        values.forEach { (name, value) -> encoded[name] = replacements?.getValue(name) ?: value }
        return json.decodeFromJsonElement<Settings>(JsonObject(encoded)).copy(
            // The serializer deliberately excludes request-scoped runtime state.
            // An editor cannot reset or manufacture it while merging stored fields.
            runtimeTranslationContext = latest.runtimeTranslationContext,
            runtimeTranslationPromptContext = latest.runtimeTranslationPromptContext,
            runtimeTranslationVisualContext = latest.runtimeTranslationVisualContext,
            runtimeTranslationScopePackage = latest.runtimeTranslationScopePackage,
            runtimeTranslationScopeLabel = latest.runtimeTranslationScopeLabel,
        )
    }

    override fun toString(): String = "SettingsEditorChanges(<redacted>)"

    companion object {
        private val json = Json { encodeDefaults = true }

        fun between(baseline: Settings, draft: Settings): SettingsEditorChanges {
            val before = json.encodeToJsonElement(baseline).jsonObject
            val after = json.encodeToJsonElement(draft).jsonObject
            return SettingsEditorChanges(after.filter { (name, value) -> before[name] != value })
        }
    }
}

/** The merge runs against the value inside DataStore's serialized update, never a prior read. */
internal suspend fun SettingsRepository.saveEditorChanges(
    baseline: Settings,
    draft: Settings,
    normalizedDraft: Settings = draft,
): Settings {
    val changes = withContext(Dispatchers.Default) { SettingsEditorChanges.between(baseline, draft) }
    update { latest -> changes.applyTo(latest, normalizedDraft) }
    return get()
}
