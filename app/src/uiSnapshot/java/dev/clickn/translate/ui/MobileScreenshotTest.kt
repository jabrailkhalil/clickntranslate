package dev.clickn.translate.ui

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.ui.theme.*
import org.junit.Rule
import org.junit.Test

/** Run explicitly with -PuiSnapshots. These render production Compose screen content. */
class MobileScreenshotTest {
    @get:Rule val paparazzi = Paparazzi(deviceConfig = DeviceConfig.PIXEL_5.copy(locale = "ru"),
        theme = "android:Theme.Material.Light.NoActionBar")
    private val settings = Settings(translatorEngine = TranslatorEngine.GOOGLE, targetLang = "ru")

    @Test fun homeLight() { home(ThemeMode.LIGHT) }
    @Test fun homeDark() { home(ThemeMode.DARK) }
    @Test fun homeBlack() { home(ThemeMode.AMOLED) }
    private fun home(mode: Int) {
        paparazzi.snapshot {
            ClickTranslateTheme(mode) {
                Surface(Modifier.fillMaxSize()) {
                    ScreenHome(settings, false, true, {}, {}, {}, {}, {}, {}, {}, {})
                }
            }
        }
    }

    @Test fun textResult() {
        paparazzi.snapshot {
            ClickTranslateTheme(ThemeMode.LIGHT) {
                Surface(Modifier.fillMaxSize()) {
                    TextWorkspace(settings, "A small step opens a new world.",
                        MobileTranslationState(result = "Маленький шаг открывает новый мир."), {}, {}, {}, {}, {}, {})
                }
            }
        }
    }

    @Test fun settingsHub() {
        paparazzi.snapshot {
            CompositionLocalProvider(LocalThemeMode provides ThemeModeController(ThemeMode.LIGHT, {}),
                LocalThemeAccent provides ThemeAccentController(ThemeAccent.LAVENDER, {})) {
                ClickTranslateTheme(ThemeMode.LIGHT) {
                    Surface(Modifier.fillMaxSize()) { SettingsHub(settings, {}, {}, {}, {}, {}, {}, {}) }
                }
            }
        }
    }
}
