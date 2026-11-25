package dev.clickn.translate.data

import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences

/**
 * Per-key value-CAS compensation, not cross-store isolation or writer identity.
 * A later different value is retained; same-value/ABA writes have no revision metadata.
 * An optional writer makes the intent durable before DataStore commits.
 */
internal class SettingsImportRollback(
    private val persist: ((List<ImportPreferenceChange>) -> Unit)? = null,
) {
    private class Change(
        val key: Preferences.Key<*>,
        val before: Any?,
        val after: Any?,
    )

    @Volatile private var changes: List<Change> = emptyList()
    private var recorded = false

    internal fun record(before: Map<Preferences.Key<*>, Any>, after: Map<Preferences.Key<*>, Any>) {
        check(!recorded) { "A settings import checkpoint cannot be reused." }
        recorded = true
        changes = (before.keys + after.keys).mapNotNull { key ->
            if (before[key] == after[key]) null else Change(key, before[key], after[key])
        }
        persist?.invoke(changes.map {
            ImportPreferenceChange(it.key.name, ImportPreferenceValues.encode(it.before), ImportPreferenceValues.encode(it.after))
        })
    }

    @Suppress("UNCHECKED_CAST")
    internal fun restore(
        preferences: MutablePreferences,
        equivalent: (Preferences.Key<*>, Any?, Any?) -> Boolean,
    ) {
        changes.forEach { change ->
            val key = change.key as Preferences.Key<Any>
            // Restore only a value still equivalent to the imported after-snapshot.
            if (equivalent(key, preferences[key], change.after)) {
                val previous = change.before
                if (previous == null) preferences.remove(key) else preferences[key] = previous
            }
        }
    }

    override fun toString(): String = "SettingsImportRollback(<redacted>)"

    internal companion object {
        fun restoreToken(snapshot: List<ImportPreferenceChange>): SettingsImportRollback = SettingsImportRollback().also { token ->
            token.recorded = true
            token.changes = snapshot.map { item ->
                val kind = checkNotNull(item.after ?: item.before) { "Empty private preference change." }
                Change(ImportPreferenceValues.key(item.name, kind),
                    item.before?.let(ImportPreferenceValues::decode), item.after?.let(ImportPreferenceValues::decode))
            }
        }
    }
}
