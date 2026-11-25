// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui

import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.SettingsEditorChanges
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.withContext

/** Memory only: neither the draft's secrets nor its dirty-check baseline belong in SavedState. */
internal class SettingsEditingSnapshot(
    val persisted: Settings,
    val draft: Settings,
    val formBaseline: Settings? = null,
) {
    override fun toString(): String = "SettingsEditingSnapshot(<redacted>)"
}

internal fun rebaseSettingsEditingSnapshot(editing: SettingsEditingSnapshot, latest: Settings): SettingsEditingSnapshot =
    SettingsEditingSnapshot(latest,
        SettingsEditorChanges.between(editing.formBaseline ?: editing.persisted, editing.draft).applyTo(latest))

/** Updates clean fields without replacing edits made while a repository emission was being mapped. */
internal suspend fun observeSettingsEditing(
    initial: SettingsEditingSnapshot,
    updates: Flow<Settings>,
    current: () -> SettingsEditingSnapshot,
    apply: (SettingsEditingSnapshot) -> Unit,
) {
    apply(initial)
    updates.collectLatest { latest ->
        while (true) {
            val before = current()
            if (before.persisted == latest) break
            val rebased = withContext(Dispatchers.Default) { rebaseSettingsEditingSnapshot(before, latest) }
            val now = current()
            if (now.persisted != before.persisted || now.draft != before.draft || now.formBaseline != before.formBaseline) continue
            apply(rebased)
            break
        }
    }
}

/** Restore a retained edit synchronously, before an initial repository read can suspend the UI. */
internal suspend fun loadSettingsEditingSnapshot(
    retained: SettingsEditingSnapshot?,
    load: suspend () -> Settings,
): SettingsEditingSnapshot = retained ?: load().let { SettingsEditingSnapshot(it, it) }

/** One initial read; migration reuses that snapshot and never replaces a concurrent custom prompt. */
internal suspend fun loadSettingsForScreen(
    read: suspend () -> Settings,
    update: suspend ((Settings) -> Settings) -> Unit,
    currentDefault: String,
    knownDefaults: () -> List<String>,
): Settings {
    val initial = read()
    if (initial.promptTemplate == currentDefault || initial.promptTemplate !in knownDefaults()) {
        return initial
    }
    var result = initial
    update { latest ->
        val next = if (latest.promptTemplate == initial.promptTemplate) {
            latest.copy(promptTemplate = currentDefault)
        } else {
            latest
        }
        result = next
        next
    }
    return result
}
