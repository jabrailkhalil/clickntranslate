package dev.clickn.translate.data

import android.content.Context
import android.content.SharedPreferences
import androidx.annotation.DrawableRes
import androidx.annotation.StringRes
import dev.clickn.translate.R

internal enum class AppCompanion(
    val id: String, @StringRes val label: Int, @DrawableRes val image: Int,
) {
    CHESTER("chester", R.string.companion_chester, R.drawable.companion_chester),
    DOC("doc", R.string.companion_doc, R.drawable.companion_doc),
    PANCAKE("pancake", R.string.companion_pancake, R.drawable.companion_pancake),
    MOCHI("mochi", R.string.companion_mochi, R.drawable.companion_mochi),
    BUBU("bubu", R.string.companion_bubu, R.drawable.companion_bubu),
    MOMO("momo", R.string.companion_momo, R.drawable.companion_momo),
}

/** Button appearance is independent of its action and of the installed launcher icon. */
internal object CompanionPrefs {
    const val ACTION = "action"
    const val LOGO = "logo"
    const val CUSTOM = "custom"
    private fun prefs(context: Context) = context.getSharedPreferences("clickn_floating_picture", Context.MODE_PRIVATE)
    private fun normalized(choice: String?): String =
        choice?.takeIf { it in setOf(ACTION, LOGO, CUSTOM) || AppCompanion.entries.any { c -> c.id == it } } ?: AppCompanion.CHESTER.id

    fun keepVisible(context: Context): Boolean = prefs(context).getBoolean("keep_visible", false)
    fun setKeepVisible(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean("keep_visible", enabled)
            .putLong("revision", prefs(context).getLong("revision", 0) + 1).apply()
    }

    fun read(context: Context): String = normalized(prefs(context).getString("choice", AppCompanion.CHESTER.id))
    fun write(context: Context, choice: String) {
        require(normalized(choice) == choice)
        prefs(context).edit().putString("choice", choice)
            .putLong("revision", prefs(context).getLong("revision", 0) + 1).apply()
    }
    fun observe(context: Context, onChanged: () -> Unit): () -> Unit {
        val preferences = prefs(context)
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == "revision") onChanged()
        }
        preferences.registerOnSharedPreferenceChangeListener(listener)
        return { preferences.unregisterOnSharedPreferenceChangeListener(listener) }
    }
}
