package dev.clickn.translate.ui

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.onboarding.OnboardingPrefs
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "en-rUS-w360dp-h800dp")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class ProviderAdvancedNavigationRuntimeTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun invalidLingvaAddressCanLeaveForAdvancedWithoutOverwritingTheWorkingProvider() =
        navigate(TranslatorEngine.LINGVA, "bad-address", valid = false)

    @Test fun invalidLibreTranslateAddressAlsoLeavesItsStoredKeyUnchanged() =
        navigate(TranslatorEngine.LIBRETRANSLATE, "https://example.invalid/?broken=true", valid = false)

    @Test fun aValidAddressStillSavesAndSelectsThatProviderBeforeOpeningAdvanced() =
        navigate(TranslatorEngine.LINGVA, "https://new.example.invalid", valid = true)

    private fun navigate(engine: TranslatorEngine, address: String, valid: Boolean) {
        val app = ApplicationProvider.getApplicationContext<ClickTranslateApp>()
        OnboardingPrefs.markCompleted(app)
        val oldAddress = "https://saved.example.invalid"
        val oldKey = "test-key-before-edit"
        val repo = app.settingsRepository
        runBlocking { repo.update { it.copy(translatorEngine = TranslatorEngine.GOOGLE,
            lingvaBaseUrl = oldAddress, libreTranslateBaseUrl = oldAddress, libreTranslateApiKey = oldKey) } }
        fun button(id: Int) = hasText(app.getString(id)) and hasClickAction()
        ActivityScenario.launch(MainActivity::class.java).use {
            val settings = button(R.string.mobile_nav_settings)
            compose.waitUntil(15_000) { compose.onAllNodes(settings).fetchSemanticsNodes().isNotEmpty() }
            compose.onNode(settings).performClick()
            val service = button(R.string.mobile_provider)
            compose.onNodeWithTag("settings-hub").performScrollToNode(service)
            compose.onNode(service).performClick()
            val choice = hasText(providerName(engine)) and hasClickAction() and hasAnyAncestor(hasTestTag("translation-services"))
            compose.onNodeWithTag("translation-services").performScrollToNode(choice)
            compose.onNode(choice).performClick()

            val form = compose.onNodeWithTag("provider-form")
            val fields = compose.onAllNodes(hasSetTextAction() and hasAnyAncestor(hasTestTag("provider-form")))
            form.performScrollToNode(hasSetTextAction())
            fields[0].assertTextContains(oldAddress).performTextReplacement(address)
            if (engine == TranslatorEngine.LIBRETRANSLATE) fields[1].performTextReplacement("uncommitted-test-key")
            val save = compose.onNodeWithTag("provider-save")
            form.performScrollToNode(hasTestTag("provider-save"))
            if (valid) save.assertIsEnabled() else {
                save.assertIsNotEnabled()
                compose.onNode(button(R.string.mobile_test)).assertIsNotEnabled()
            }
            form.performScrollToNode(hasTestTag("provider-advanced"))
            compose.onNodeWithTag("provider-advanced").assertIsEnabled().performClick()
            compose.waitUntil(15_000) { compose.onAllNodesWithTag("provider-form").fetchSemanticsNodes().isEmpty() }
            val general = button(R.string.refine_general)
            compose.onNode(hasScrollAction()).performScrollToNode(general)
            compose.onNode(general).assertIsDisplayed()
        }
        val stored = runBlocking { repo.get() }
        assertEquals(if (valid) engine else TranslatorEngine.GOOGLE, stored.translatorEngine)
        assertEquals(if (valid && engine == TranslatorEngine.LINGVA) address else oldAddress, stored.lingvaBaseUrl)
        assertEquals(oldAddress, stored.libreTranslateBaseUrl)
        assertEquals(oldKey, stored.libreTranslateApiKey)
    }
}
