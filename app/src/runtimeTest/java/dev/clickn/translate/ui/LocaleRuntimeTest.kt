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
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "en-rUS")
@LooperMode(LooperMode.Mode.PAUSED)
class LocaleRuntimeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    @Test fun russianChoiceAppliesToStartupImmediately() {
        setupClick("Interface language")
        compose.onNodeWithText("Русский").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Начать с этими настройками").performScrollTo().assertIsDisplayed()
        assertEquals("ru", AppLocalePrefs.read(compose.activity))
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        compose.onNodeWithText("Начать с этими настройками").performScrollTo().assertIsDisplayed()
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
            setupClick(label)
            compose.onNodeWithText(name).performClick()
            compose.waitForIdle()
            compose.onNodeWithText(start).performScrollTo().assertIsDisplayed()
            label = nextLabel
        }
    }
    @Test fun paperThemePersistsAcrossRecreation() {
        setupClick("Appearance")
        compose.onNodeWithTag("appearance-options").performScrollToNode(hasText("Paper Night"))
        compose.onNodeWithText("Paper Night").performClick()
        assertEquals(ThemeMode.PAPER_NIGHT, ThemeModePrefs.read(compose.activity))
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        assertEquals(ThemeMode.PAPER_NIGHT, ThemeModePrefs.read(compose.activity))
        val controller = androidx.core.view.WindowCompat.getInsetsController(compose.activity.window, compose.activity.window.decorView)
        assertFalse(controller.isAppearanceLightStatusBars)
    }
    private fun setupClick(label: String) {
        compose.onNodeWithTag("setup-options").performScrollToNode(hasText(label))
        compose.onNodeWithText(label).performClick()
    }
    private fun listClick(label: String) {
        val row = hasText(label) and hasClickAction()
        compose.onNode(hasScrollAction()).performScrollToNode(row)
        compose.onNode(row).performClick()
    }
    private fun resource(id: Int) = compose.activity.getString(id)
    private fun openAdvanced() {
        compose.runOnIdle { AppLocalePrefs.write(compose.activity, "en") }
        compose.waitForIdle()
        compose.onNodeWithText(resource(R.string.refine_quick_setup)).performScrollTo().performClick()
        compose.onNodeWithText(resource(R.string.mobile_nav_settings)).performClick()
        compose.waitUntil(10_000) { compose.onAllNodes(hasScrollAction()).fetchSemanticsNodes().isNotEmpty() }
        listClick(resource(R.string.mobile_advanced))
    }
    @Test fun displayModeChoiceSavesTheActualSetting() {
        val repo = (compose.activity.application as ClickTranslateApp).settingsRepository
        kotlinx.coroutines.runBlocking { repo.update { it.copy(renderMode = dev.clickn.translate.data.RenderMode.BLOCKS) } }
        openAdvanced()
        listClick(resource(R.string.refine_overlay))
        compose.onNodeWithText(resource(R.string.settings_render_floating_window_chip)).performScrollTo().performClick()
        compose.onNodeWithText(resource(R.string.settings_save_btn), useUnmergedTree = true).performClick()
        compose.waitUntil(10_000) { kotlinx.coroutines.runBlocking { repo.get().renderMode == dev.clickn.translate.data.RenderMode.FLOATING_WINDOW } }
    }
    @Test fun languageRecreationPreservesUnsavedSettingsDraft() {
        val repo = (compose.activity.application as ClickTranslateApp).settingsRepository
        kotlinx.coroutines.runBlocking { repo.update { it.copy(renderMode = dev.clickn.translate.data.RenderMode.BLOCKS) } }
        openAdvanced()
        listClick(resource(R.string.refine_overlay))
        compose.onNodeWithText(resource(R.string.settings_render_floating_window_chip)).performScrollTo().performClick()
        compose.onNodeWithContentDescription(resource(R.string.common_back)).performClick()
        listClick(resource(R.string.refine_general))
        compose.onNodeWithText(resource(R.string.settings_app_lang_en)).performClick()
        compose.onNodeWithText(resource(R.string.settings_app_lang_ru)).performClick()
        compose.waitForIdle()
        compose.onNodeWithContentDescription(resource(R.string.common_back)).performClick()
        listClick(resource(R.string.refine_overlay))
        compose.onNodeWithText(resource(R.string.settings_render_floating_window_chip)).performScrollTo().assertIsSelected()
        assertEquals(dev.clickn.translate.data.RenderMode.BLOCKS, kotlinx.coroutines.runBlocking { repo.get().renderMode })
        compose.onNodeWithText(resource(R.string.settings_save_btn), useUnmergedTree = true).performClick()
        compose.waitUntil(10_000) { kotlinx.coroutines.runBlocking { repo.get().renderMode == dev.clickn.translate.data.RenderMode.FLOATING_WINDOW } }
    }

}
