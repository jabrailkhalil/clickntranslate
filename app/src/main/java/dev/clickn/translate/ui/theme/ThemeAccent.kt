package dev.clickn.translate.ui.theme

import android.content.Context
import androidx.compose.runtime.compositionLocalOf
import dev.clickn.translate.R

enum class ThemeAccent(val lightColor: Long, val darkColor: Long, val label: Int) {
    LAVENDER(0xFF6F3BBB, 0xFFB69AF7, R.string.mobile_lavender),
    OCEAN(0xFF00649D, 0xFF8ACEFF, R.string.mobile_ocean),
    MINT(0xFF006C50, 0xFF7BE7B7, R.string.mobile_mint),
    ROSE(0xFFA53765, 0xFFFFAFCA, R.string.mobile_rose),
    MONO(0xFF46505C, 0xFFD2DBE8, R.string.mobile_mono),
}

object ThemeAccentPrefs {
    fun read(context: Context): ThemeAccent = runCatching {
        ThemeAccent.valueOf(context.getSharedPreferences("clickn_appearance", Context.MODE_PRIVATE)
            .getString("accent", ThemeAccent.LAVENDER.name)!!)
    }.getOrDefault(ThemeAccent.LAVENDER)

    fun write(context: Context, accent: ThemeAccent) {
        context.getSharedPreferences("clickn_appearance", Context.MODE_PRIVATE).edit()
            .putString("accent", accent.name).apply()
    }
}

data class ThemeAccentController(val accent: ThemeAccent, val setAccent: (ThemeAccent) -> Unit)
val LocalThemeAccent = compositionLocalOf<ThemeAccentController> { error("Theme accent controller missing") }
