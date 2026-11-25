package dev.clickn.translate.history

import android.content.Context

/** Used only for one-time import and explicit history removal, always from the repository IO context. */
internal class SharedPreferencesTextHistorySource(
    private val context: Context,
    private val name: String = "clickn_text_history",
) : LegacyTextHistorySource {
    private fun preferences() = context.getSharedPreferences(name, Context.MODE_PRIVATE)
    override suspend fun read(): String = preferences().getString("entries", "[]") ?: "[]"
    override suspend fun erase() {
        check(preferences().edit().remove("entries").commit()) { "History cleanup failed" }
    }
}
