package dev.clickn.translate.ui

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Rect
import android.os.ParcelFileDescriptor
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.TranslatorEngine
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

    @Test fun leavingAnInvalidLibreAddressPreservesAKeyBackedByTheDeviceKeystore() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("providerRotation") == "true")
        val app = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext as ClickTranslateApp
        val repo = app.settingsRepository
        val original = runBlocking { repo.get() }
        val savedKey = "disposable-avd-fixture-key"
        val savedUrl = "https://saved.example.invalid"
        fun button(id: Int) = hasText(app.getString(id)) and hasClickAction()
        try {
            runBlocking {
                repo.update { it.copy(translatorEngine = TranslatorEngine.GOOGLE, libreTranslateBaseUrl = savedUrl,
                    libreTranslateApiKey = savedKey) }
                assertEquals("The real Android keystore must preserve the fixture before editing", savedKey, repo.get().libreTranslateApiKey)
            }
            ActivityScenario.launch(MainActivity::class.java).use {
                val settings = button(R.string.mobile_nav_settings)
                compose.waitUntil(15_000) { compose.onAllNodes(settings).fetchSemanticsNodes().isNotEmpty() }
                compose.onNode(settings).performClick()
                val service = button(R.string.mobile_provider)
                compose.onNodeWithTag("settings-hub").performScrollToNode(service)
                compose.onNode(service).performClick()
                val libre = hasText("LibreTranslate") and hasClickAction() and hasAnyAncestor(hasTestTag("translation-services"))
                compose.onNodeWithTag("translation-services").performScrollToNode(libre)
                compose.onNode(libre).performClick()
                val form = compose.onNodeWithTag("provider-form")
                val fields = compose.onAllNodes(hasSetTextAction() and hasAnyAncestor(hasTestTag("provider-form")))
                form.performScrollToNode(hasSetTextAction())
                fields[0].assertTextContains(savedUrl).performTextReplacement("bad-address")
                fields[1].performTextReplacement("unused-draft-key")
                form.performScrollToNode(hasTestTag("provider-save"))
                compose.onNodeWithTag("provider-save").assertIsNotEnabled()
                form.performScrollToNode(hasTestTag("provider-advanced"))
                compose.onNodeWithTag("provider-advanced").assertIsEnabled().performClick()
                compose.waitUntil(10_000) { compose.onAllNodesWithTag("provider-form").fetchSemanticsNodes().isEmpty() }
                val general = button(R.string.refine_general)
                compose.onNode(hasScrollAction()).performScrollToNode(general)
                compose.onNode(general).assertIsDisplayed()
                val stored = runBlocking { repo.get() }
                assertEquals(TranslatorEngine.GOOGLE, stored.translatorEngine)
                assertEquals(savedUrl, stored.libreTranslateBaseUrl)
                assertEquals(savedKey, stored.libreTranslateApiKey)
            }
        } finally {
            runBlocking { repo.update { it.copy(translatorEngine = original.translatorEngine,
                libreTranslateBaseUrl = original.libreTranslateBaseUrl, libreTranslateApiKey = original.libreTranslateApiKey) } }
        }
    }

    @Test fun largeTextLandscapeEditorCanDiscardAndSaveWithTheKeyboardOpen() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        assumeTrue("Opt-in companion to the emulator onboarding journey",
            InstrumentationRegistry.getArguments().getString("providerRotation") == "true")
        val app = instrumentation.targetContext.applicationContext as ClickTranslateApp
        assertTrue("Finish the first-run journey before testing the settings hub", OnboardingPrefs.isCompleted(app))
        val original = runBlocking { app.settingsRepository.get() }
        val syntheticServer = "https://example.invalid/pending-translation"
        val output = File(app.filesDir, "qa-provider-rotation").apply { mkdirs() }
        val ui = instrumentation.uiAutomation
        fun shell(command: String) = ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand(command))
            .bufferedReader().use { it.readText().trim() }
        fun restoreSetting(table: String, name: String, value: String) {
            if (value == "null") shell("settings delete $table $name") else shell("settings put $table $name $value")
        }
        fun keyboardVisible() = ui.windows.any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
        fun saveOnScreen(): Rect? {
            val label = app.getString(R.string.mobile_save)
            fun visibleButton(node: AccessibilityNodeInfo): Rect? {
                if (node.isVisibleToUser && (node.text?.toString() == label || node.contentDescription?.toString() == label)) {
                    val bounds = Rect().also(node::getBoundsInScreen)
                    if (!bounds.isEmpty) return bounds
                }
                for (index in 0 until node.childCount) {
                    val child = node.getChild(index) ?: continue
                    visibleButton(child)?.let { return it }
                }
                return null
            }
            for (window in ui.windows) {
                if (window.type != AccessibilityWindowInfo.TYPE_APPLICATION) continue
                val root = window.root ?: continue
                if (root.packageName != app.packageName) continue
                // Compose exposes virtual children. A provider's platform text-search shortcut
                // need not enumerate them even when those children are visible to TalkBack.
                visibleButton(root)?.let { return it }
            }
            return null
        }

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

        fun exerciseForm() = ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT }
            compose.waitUntil(15_000) {
                val config = app.resources.configuration
                config.orientation == Configuration.ORIENTATION_PORTRAIT && config.fontScale >= 1.3f
            }
            val settingsTab = hasText(app.getString(R.string.mobile_nav_settings)) and hasClickAction()
            compose.waitUntil(15_000) { compose.onAllNodes(settingsTab).fetchSemanticsNodes().isNotEmpty() }
            compose.onNode(settingsTab).performClick()
            openService()
            fun serverField() = compose.onNode(hasSetTextAction() and hasAnyAncestor(hasTestTag("provider-form")))
            serverField().performTextReplacement(syntheticServer)
            serverField().assertTextContains(syntheticServer)
            assertEquals(original.lingvaBaseUrl, runBlocking { app.settingsRepository.get().lingvaBaseUrl })
            val testLabel = app.getString(R.string.mobile_test)
            compose.onNodeWithTag("provider-form").performScrollToNode(hasText(testLabel))
            compose.onNodeWithText(testLabel, useUnmergedTree = true)
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { read ->
                    val results = mutableListOf<TextLayoutResult>()
                    assertTrue(read(results))
                    assertEquals("The narrow button must not split connection across lines", 1, results.single().lineCount)
                }
            capture("portrait")

            scenario.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE }
            compose.waitUntil(15_000) { app.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE }
            compose.onNodeWithTag("provider-form").performScrollToNode(hasSetTextAction())
            serverField().assertIsDisplayed().assertTextContains(syntheticServer)
            if (keyboardVisible()) {
                Espresso.pressBack()
                compose.waitUntil(10_000) { !keyboardVisible() }
            }
            // The resting form must show Save in landscape without dragging the sheet handle.
            compose.onNodeWithTag("provider-save").assertIsDisplayed()
            capture("landscape")
            serverField().performTouchInput { click() }
            compose.waitUntil(10_000) { keyboardVisible() }
            Espresso.pressBack()
            compose.waitUntil(10_000) { !keyboardVisible() }
            serverField().assertTextContains(syntheticServer)
            Espresso.pressBack()
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("provider-form").fetchSemanticsNodes().isEmpty() }

            openService()
            assertEquals(original.lingvaBaseUrl, serverField().fetchSemanticsNode().config[SemanticsProperties.EditableText].text)
            assertEquals(original.translatorEngine, runBlocking { app.settingsRepository.get().translatorEngine })
            serverField().performTouchInput { click() }
            compose.waitUntil(10_000) { keyboardVisible() }
            serverField().performTextReplacement(syntheticServer)
            compose.onNodeWithTag("provider-form").performScrollToNode(hasTestTag("provider-save"))
            compose.onNodeWithTag("provider-save").assertIsDisplayed().assertIsEnabled()
            assertTrue("Keep the real keyboard open during Save", keyboardVisible())
            capture("landscape-ime")
            compose.waitUntil(10_000) { saveOnScreen() != null }
            val button = requireNotNull(saveOnScreen())
            // A system input tap also verifies that the IME is not covering the touch target.
            shell("input tap ${button.centerX()} ${button.centerY()}")
            compose.waitUntil(10_000) { compose.onAllNodesWithTag("provider-form").fetchSemanticsNodes().isEmpty() }
            val saved = runBlocking { app.settingsRepository.get() }
            assertEquals(syntheticServer, saved.lingvaBaseUrl)
            assertEquals(TranslatorEngine.LINGVA, saved.translatorEngine)
        }

        val previousScale = shell("settings get system font_scale")
        val previousKeyboard = shell("settings get secure show_ime_with_hard_keyboard")
        val previousFlags = ui.serviceInfo.flags
        try {
            shell("settings put system font_scale 1.3")
            shell("settings put secure show_ime_with_hard_keyboard 1")
            ui.serviceInfo = ui.serviceInfo.apply {
                flags = previousFlags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS or
                    AccessibilityServiceInfo.FLAG_INCLUDE_NOT_IMPORTANT_VIEWS
            }
            exerciseForm()
        } finally {
            ui.serviceInfo = ui.serviceInfo.apply { flags = previousFlags }
            restoreSetting("secure", "show_ime_with_hard_keyboard", previousKeyboard)
            restoreSetting("system", "font_scale", previousScale)
            runBlocking {
                app.settingsRepository.update { it.copy(lingvaBaseUrl = original.lingvaBaseUrl, translatorEngine = original.translatorEngine) }
            }
        }
    }
}
