// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.ui.theme

import androidx.compose.runtime.compositionLocalOf

/**
 * 主题模式 controller：当前 mode + 修改入口。
 *
 * 由 MainActivity 顶层以 [androidx.compose.runtime.CompositionLocalProvider] 提供，
 * 设置页通过 [LocalThemeMode] 读取与修改。修改后 [ClickTranslateTheme] 重新组合即生效，
 * 无需重建 Activity。
 */
class ThemeModeController(
    val mode: Int,
    val setMode: (Int) -> Unit
)

val LocalThemeMode = compositionLocalOf<ThemeModeController> {
    error("LocalThemeMode not provided. Wrap content with CompositionLocalProvider in MainActivity.")
}
