package dev.clickn.translate.ui

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.background
import androidx.compose.ui.graphics.Color
import dev.clickn.translate.R
import dev.clickn.translate.data.RenderMode
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
    @Test fun homePaperDay() { home(ThemeMode.PAPER_DAY) }
    @Test fun homePaperNight() { home(ThemeMode.PAPER_NIGHT) }
    @Test fun homePaperNord() { home(ThemeMode.PAPER_NORD) }
    @Test fun homeBlack() { home(ThemeMode.AMOLED) }
    private fun home(mode: Int) {
        paparazzi.snapshot {
            CompositionLocalProvider(LocalThemeMode provides ThemeModeController(mode, {})) {
                ClickTranslateTheme(mode) {
                    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).komiPaperGrid(mode, MaterialTheme.colorScheme.onBackground)) {
                        ScreenHome(settings, false, true, {}, {}, {}, {}, {}, {}, {}, {})
                    }
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
    @Test fun advancedDirectory() = render { AdvancedSettingsDirectory(settings, {}) }
    @Test fun displayModeChoices() = render {
        Column(Modifier.padding(24.dp)) {
            BrandLogo(Modifier.size(64.dp))
            SectionCard("Как показывать перевод") {
                SettingChoiceCards(RenderMode.FLOATING_WINDOW, listOf(RenderMode.BLOCKS to R.string.settings_render_blocks_chip,
                    RenderMode.FLOATING_WINDOW to R.string.settings_render_floating_window_chip), {})
            }
        }
    }
    @Test fun paperDisplayModeChoices() = render(ThemeMode.PAPER_NIGHT) {
        Column(Modifier.padding(24.dp)) {
            SectionCard("Как показывать перевод") {
                SettingChoiceCards(RenderMode.BLOCKS, listOf(RenderMode.BLOCKS to R.string.settings_render_blocks_chip,
                    RenderMode.FLOATING_WINDOW to R.string.settings_render_floating_window_chip), {})
            }
        }
    }
    @Test fun readiness() = render {
        Box(Modifier.padding(24.dp)) { MobileReadinessPanel(settings, MobileModelState(false, true, true), false, false, true, false, {}, {}, {}, {}, {}, {}, {}) }
    }
    @Test fun brandIcons() = render {
        Row(Modifier.padding(24.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            BrandLogo(Modifier.size(96.dp)); BrandLogo(Modifier.size(96.dp), BrandIconPrefs.MASCOT)
        }
    }
    @Test fun translationReviewHelp() = render {
        Column(Modifier.padding(24.dp)) { TranslationReviewHelpIllustration() }
    }
    private fun render(mode: Int = ThemeMode.LIGHT, content: @androidx.compose.runtime.Composable () -> Unit) {
        paparazzi.snapshot {
            CompositionLocalProvider(LocalThemeMode provides ThemeModeController(mode, {})) {
                ClickTranslateTheme(mode) { Surface(Modifier.fillMaxSize()) { content() } }
            }
        }
    }

}
