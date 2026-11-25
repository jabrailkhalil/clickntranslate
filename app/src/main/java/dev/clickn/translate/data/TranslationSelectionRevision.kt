package dev.clickn.translate.data

import androidx.datastore.preferences.core.MutablePreferences
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.longPreferencesKey

/** One store emission; unrelated settings do not participate in selection ownership. */
internal data class TranslationSelectionSnapshot(val settings: Settings, val revision: Long) {
    fun matches(current: Settings, currentRevision: Long): Boolean =
        revision == currentRevision && TranslationSelectionRevision.sameSelection(settings, current)
}

/** Local concurrency metadata, deliberately outside portable Settings and import compensation. */
internal object TranslationSelectionRevision {
    val key = longPreferencesKey("translation_selection_revision")

    fun read(preferences: Preferences): Long = preferences[key] ?: 0L

    fun sameSelection(before: Settings, after: Settings): Boolean =
        before.translatorEngine == after.translatorEngine &&
            before.sourceLang == after.sourceLang && before.targetLang == after.targetLang

    fun advanceIfChanged(preferences: MutablePreferences, before: Settings, after: Settings) {
        // This records effective value changes, not repeated same-value UI intent.
        if (!sameSelection(before, after)) preferences[key] = Math.incrementExact(read(preferences))
    }
}
