// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.data

import android.content.Context
import dev.clickn.translate.ui.theme.ThemeMode

/**
 * 夜间模式偏好的同步持久化。用 SharedPreferences 而非 DataStore 是为了 onCreate 同步读取，
 * 避免主题在首帧后才生效造成"白闪"。
 *
 * 值为 [ThemeMode] 中的常量（0=跟随系统 / 1=白天 / 2=夜间）。
 */
object ThemeModePrefs {
    private const val FILE = "theme_prefs"
    private const val KEY_MODE = "night_mode"

    fun read(context: Context): Int {
        val raw = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .getInt(KEY_MODE, ThemeMode.FOLLOW_SYSTEM)
        // 兼容旧版本写入的 AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM = -1：
        // 1 和 2 与新常量恰好同值，其它视为跟随系统。
        return when (raw) {
            ThemeMode.LIGHT, ThemeMode.DARK, ThemeMode.AMOLED, ThemeMode.PAPER_DAY, ThemeMode.PAPER_NIGHT, ThemeMode.PAPER_NORD -> raw
            else -> ThemeMode.FOLLOW_SYSTEM
        }
    }

    fun write(context: Context, mode: Int) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
            .edit()
            .putInt(KEY_MODE, mode)
            .apply()
    }
}
