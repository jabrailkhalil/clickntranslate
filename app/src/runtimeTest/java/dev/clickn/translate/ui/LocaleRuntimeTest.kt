package dev.clickn.translate.ui

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.data.ThemeModePrefs
import dev.clickn.translate.ui.theme.ThemeMode
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class)
@LooperMode(LooperMode.Mode.PAUSED)
class LocaleRuntimeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    @Test fun russianChoiceAppliesToStartupImmediately() {
        compose.onNodeWithText("Interface language").performClick()
        compose.onNodeWithText("Русский").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Начать с этими настройками").assertIsDisplayed()
        assertEquals("ru", AppLocalePrefs.read(compose.activity))
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        compose.onNodeWithText("Начать с этими настройками").assertIsDisplayed()
    }
    @Test fun allSixInterfaceLanguagesApplyInActualActivity() {
        val choices = listOf(
            Triple("Русский", "Начать с этими настройками", "Язык интерфейса"),
            Triple("Deutsch", "Mit diesen Einstellungen starten", "App-Sprache"),
            Triple("Français", "Démarrer avec ces réglages", "Langue de l’interface"),
            Triple("Español", "Empezar con estos ajustes", "Idioma de la interfaz"),
            Triple("中文", "使用这些设置开始", "界面语言"),
            Triple("English", "Start with these settings", "Interface language"),
        )
        var label = "Interface language"
        choices.forEach { (name, start, nextLabel) ->
            compose.onNodeWithText(label).performClick()
            compose.onNodeWithText(name).performClick()
            compose.waitForIdle()
            compose.onNodeWithText(start).assertIsDisplayed()
            label = nextLabel
        }
    }
    @Test fun paperThemePersistsAcrossRecreation() {
        compose.onNodeWithText("Appearance").performClick()
        compose.onNodeWithTag("appearance-options").performScrollToNode(hasText("Paper Night"))
        compose.onNodeWithText("Paper Night").performClick()
        assertEquals(ThemeMode.PAPER_NIGHT, ThemeModePrefs.read(compose.activity))
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        assertEquals(ThemeMode.PAPER_NIGHT, ThemeModePrefs.read(compose.activity))
        val controller = androidx.core.view.WindowCompat.getInsetsController(compose.activity.window, compose.activity.window.decorView)
        assertFalse(controller.isAppearanceLightStatusBars)
    }
}
