package dev.clickn.translate.ui

import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.onboarding.OnboardingPrefs
import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProviderEditorRotationIntegrationTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun unsavedServerSurvivesRotationAndDismissRestoresTheSavedValue() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        assumeTrue("Opt-in companion to the emulator onboarding journey",
            InstrumentationRegistry.getArguments().getString("providerRotation") == "true")
        val app = instrumentation.targetContext.applicationContext as ClickTranslateApp
        assertTrue("Finish the first-run journey before testing the settings hub", OnboardingPrefs.isCompleted(app))
        val original = runBlocking { app.settingsRepository.get() }
        val syntheticServer = "https://example.invalid/pending-translation"
        val output = File(app.filesDir, "qa-provider-rotation").apply { mkdirs() }

        fun openService() {
            val service = hasText(app.getString(R.string.mobile_provider)) and hasClickAction()
            compose.onNodeWithTag("settings-hub").performScrollToNode(service)
            compose.onNode(service).performClick()
            val lingva = hasText("Lingva") and hasClickAction() and hasAnyAncestor(hasTestTag("translation-services"))
            compose.onNodeWithTag("translation-services").performScrollToNode(hasText("Lingva"))
            compose.onNode(lingva).performClick()
            compose.onNodeWithTag("provider-form").performScrollToNode(hasSetTextAction())
        }
        fun capture(name: String) {
            compose.waitForIdle()
            val bitmap = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
            try {
                File(output, "$name.png").outputStream().use { stream ->
                    assertTrue("Could not save the test screen", bitmap.compress(Bitmap.CompressFormat.PNG, 100, stream))
                }
            } finally { bitmap.recycle() }
        }

        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT }
            compose.waitUntil(15_000) { app.resources.configuration.orientation == Configuration.ORIENTATION_PORTRAIT }
            val settingsTab = hasText(app.getString(R.string.mobile_nav_settings)) and hasClickAction()
            compose.waitUntil(15_000) { compose.onAllNodes(settingsTab).fetchSemanticsNodes().isNotEmpty() }
            compose.onNode(settingsTab).performClick()
            openService()
            fun serverField() = compose.onNode(hasSetTextAction() and hasAnyAncestor(hasTestTag("provider-form")))
            serverField().performTextReplacement(syntheticServer)
            serverField().assertTextContains(syntheticServer)
            assertEquals(original.lingvaBaseUrl, runBlocking { app.settingsRepository.get().lingvaBaseUrl })
            capture("portrait")

            scenario.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE }
            compose.waitUntil(15_000) { app.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE }
            compose.onNodeWithTag("provider-form").performScrollToNode(hasSetTextAction())
            serverField().assertIsDisplayed().assertTextContains(syntheticServer)
            capture("landscape")
            repeat(3) {
                if (compose.onAllNodesWithTag("provider-form").fetchSemanticsNodes().isNotEmpty()) {
                    Espresso.pressBack()
                    compose.waitForIdle()
                }
            }
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("provider-form").fetchSemanticsNodes().isEmpty() }

            openService()
            assertEquals(original.lingvaBaseUrl, serverField().fetchSemanticsNode().config[SemanticsProperties.EditableText].text)
            assertEquals(original.translatorEngine, runBlocking { app.settingsRepository.get().translatorEngine })
        }
    }
}
