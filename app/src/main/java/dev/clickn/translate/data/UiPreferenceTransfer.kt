package dev.clickn.translate.data

import android.content.Context
import android.content.SharedPreferences
import dev.clickn.translate.ui.theme.ThemeAccentPrefs
import kotlinx.serialization.Serializable

internal enum class UiPreferenceField(val file: String, val key: String) {
    THEME("theme_prefs", "night_mode"),
    ACCENT("clickn_appearance", "accent"),
    LANGUAGE("locale_prefs", "tag"),
    COMPANION("clickn_floating_picture", "choice");

    val revisionKey get() = "portable_revision_$key"
    fun prefs(context: Context): SharedPreferences = context.getSharedPreferences(file, Context.MODE_PRIVATE)
}

@Serializable
internal data class ImportUiPreferenceChange(
    val field: UiPreferenceField,
    val before: ImportPreferenceValue?,
    val after: ImportPreferenceValue,
    val beforeRevision: Long,
) {
    override fun toString(): String = "ImportUiPreferenceChange(<redacted>)"

    fun validate() {
        check(beforeRevision in 0 until Long.MAX_VALUE)
        before?.let(ImportPreferenceValues::validate)
        val value = ImportPreferenceValues.decode(after)
        val portable = when (field) {
            UiPreferenceField.THEME -> PortableUiPreferences(themeMode = value as Int)
            UiPreferenceField.ACCENT -> PortableUiPreferences(accent = value as String)
            UiPreferenceField.LANGUAGE -> PortableUiPreferences(languageTag = value as String)
            UiPreferenceField.COMPANION -> PortableUiPreferences(companion = value as String)
        }
        portable.validate()
    }
}

/** Fixed preference registry, shared by normal UI writers and post-commit import recovery. */
internal object UiPreferenceTransfer {
    internal val mutationLock = Any()

    fun snapshot(context: Context): PortableUiPreferences = synchronized(mutationLock) {
        PortableUiPreferences(
            themeMode = ThemeModePrefs.read(context),
            accent = ThemeAccentPrefs.read(context).name,
            languageTag = AppLocalePrefs.read(context).takeIf { it in PortableUiPreferences.LANGUAGE_TAGS },
            companion = CompanionPrefs.read(context).takeIf {
                CompanionPrefs.hasSelection(context) && it in PortableUiPreferences.COMPANIONS
            },
        )
    }

    fun write(context: Context, field: UiPreferenceField, value: Any) = synchronized(mutationLock) {
        val prefs = field.prefs(context)
        publish(prefs, field, value, Math.incrementExact(prefs.getLong(field.revisionKey, 0)))
    }

    fun observe(context: Context, field: UiPreferenceField, onChange: () -> Unit): () -> Unit {
        val prefs = field.prefs(context)
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == null || key == field.key) onChange()
        }
        prefs.registerOnSharedPreferenceChangeListener(listener)
        return { prefs.unregisterOnSharedPreferenceChangeListener(listener) }
    }

    fun plan(context: Context, portable: PortableUiPreferences?): List<ImportUiPreferenceChange> {
        portable ?: return emptyList() // V1/V2 and legacy presets never replace local UI choices.
        portable.validate()
        val values = listOf(
            UiPreferenceField.THEME to portable.themeMode,
            UiPreferenceField.ACCENT to portable.accent,
            UiPreferenceField.LANGUAGE to portable.languageTag,
            UiPreferenceField.COMPANION to portable.companion,
        )
        return synchronized(mutationLock) {
            values.mapNotNull { (field, value) ->
                value ?: return@mapNotNull null
                val prefs = field.prefs(context)
                val before = ImportPreferenceValues.encode(prefs.all[field.key])
                val after = checkNotNull(ImportPreferenceValues.encode(value))
                if (before == after) null else ImportUiPreferenceChange(
                    field, before, after, prefs.getLong(field.revisionKey, 0),
                ).also { it.validate() }
            }
        }
    }

    /** Called on IO only after the encrypted journal has a durable COMMITTED decision. */
    fun applyCommitted(context: Context, changes: List<ImportUiPreferenceChange>) {
        check(changes.map { it.field }.distinct().size == changes.size)
        changes.forEach { change ->
            change.validate()
            val prefs = change.field.prefs(context)
            synchronized(mutationLock) {
                val revision = prefs.getLong(change.field.revisionKey, 0)
                val current = ImportPreferenceValues.encode(prefs.all[change.field.key])
                // A later UI choice (including change-and-revert) owns its value. Replays of
                // already applied changes only need the durability barrier below.
                if (revision == change.beforeRevision && current == change.before) {
                    publish(prefs, change.field, ImportPreferenceValues.decode(change.after), revision + 1)
                }
            }
            // Do not hold the UI writer lock during disk IO. commit waits for preceding
            // apply writes even on a retry after an earlier failed flush.
            check(prefs.edit().commit()) { "Could not persist imported interface preferences." }
        }
    }

    private fun publish(prefs: SharedPreferences, field: UiPreferenceField, value: Any, revision: Long) {
        val editor = prefs.edit().putLong(field.revisionKey, revision)
        when (value) {
            is Int -> editor.putInt(field.key, value)
            is String -> editor.putString(field.key, value)
            else -> error("Unsupported interface preference value.")
        }
        if (field == UiPreferenceField.COMPANION) {
            editor.putLong("revision", Math.incrementExact(prefs.getLong("revision", 0)))
        }
        editor.apply()
    }
}
