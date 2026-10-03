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
        assertSetupShown("Выбери тему")
        assertEquals("ru", AppLocalePrefs.read(compose.activity))
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        assertSetupShown("Выбери тему")
    }
    @Test fun allSixInterfaceLanguagesApplyInActualActivity() {
        val choices = listOf(
            Triple("Русский", "Выбери тему", "Язык интерфейса"),
            Triple("Deutsch", "Wähle ein Design", "App-Sprache"),
            Triple("Français", "Choisis un thème", "Langue de l’interface"),
            Triple("Español", "Elige un tema", "Idioma de la interfaz"),
            Triple("中文", "选择主题", "界面语言"),
            Triple("English", "Choose a theme", "Interface language"),
        )
        var label = "Interface language"
        choices.forEach { (name, start, nextLabel) ->
            setupClick(label)
            compose.onNodeWithText(name).performClick()
            compose.waitForIdle()
            assertSetupShown(start)
            label = nextLabel
        }
    }
    @Test fun paperThemePersistsAcrossRecreation() {
        compose.onNodeWithTag("setup-options").performScrollToNode(hasTestTag("theme-${ThemeMode.PAPER_NIGHT}"))
        compose.onNodeWithTag("theme-${ThemeMode.PAPER_NIGHT}").assertIsDisplayed().assertHasClickAction()
        compose.onNodeWithTag("theme-${ThemeMode.PAPER_NIGHT}").performClick()
        compose.waitForIdle()
        assertEquals(ThemeMode.PAPER_NIGHT, ThemeModePrefs.read(compose.activity))
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        assertEquals(ThemeMode.PAPER_NIGHT, ThemeModePrefs.read(compose.activity))
        val controller = androidx.core.view.WindowCompat.getInsetsController(compose.activity.window, compose.activity.window.decorView)
        assertFalse(controller.isAppearanceLightStatusBars)
    }
    @Test fun characterChoiceCanScrollSelectAndSurviveRecreation() {
        finishIntro()
        compose.onNodeWithText(resource(R.string.mobile_nav_settings)).performClick()
        listClick(resource(R.string.refine_floating))
        // Includes the last row: all companions must be reachable on a small screen.
        listOf("momo", "doc", "chester").forEach { id ->
            compose.onNodeWithTag("floating-appearance").performScrollToNode(hasTestTag("companion-$id"))
            compose.onNodeWithTag("companion-$id").assertIsDisplayed().performClick()
            compose.waitForIdle()
            assertEquals(id, dev.clickn.translate.data.CompanionPrefs.read(compose.activity))
        }
        compose.activityRule.scenario.recreate()
        compose.waitForIdle()
        assertEquals("chester", dev.clickn.translate.data.CompanionPrefs.read(compose.activity))
    }

    private fun finishIntro() {
        compose.onNodeWithText(resource(R.string.setup_next)).performClick()
        compose.waitForIdle()
        compose.onNodeWithText(resource(R.string.setup_finish)).assertIsDisplayed().performClick()
        compose.waitForIdle()
    }
    private fun assertSetupShown(label: String) {
        compose.onNodeWithTag("setup-options").performScrollToNode(hasText(label))
        compose.onNodeWithText(label).assertIsDisplayed()
    }
    private fun setupClick(label: String) {
        assertSetupShown(label)
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
        finishIntro()
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
