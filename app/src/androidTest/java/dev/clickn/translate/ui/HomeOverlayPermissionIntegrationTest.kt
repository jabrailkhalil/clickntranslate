package dev.clickn.translate.ui

import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.capture.CaptureStartMode
import dev.clickn.translate.capture.CaptureStartPreference
import dev.clickn.translate.capture.CaptureStartRequestActivity
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.onboarding.OnboardingPrefs
import dev.clickn.translate.service.CaptureServiceState
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HomeOverlayPermissionIntegrationTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun denyingOverlayAndGrantingItLaterDoesNotReplayAHomeStart() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("homeOverlayDenial") == "true")
        assertTrue("Use a disposable AVD", Build.HARDWARE == "ranchu" || Build.HARDWARE == "goldfish")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val app = instrumentation.targetContext.applicationContext as ClickTranslateApp
        val ui = instrumentation.uiAutomation
        fun shell(command: String): String = ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand(command))
            .bufferedReader().use { it.readText() }
        fun waitFor(description: String, predicate: () -> Boolean) {
            val end = SystemClock.elapsedRealtime() + 15_000
            while (!predicate() && SystemClock.elapsedRealtime() < end) SystemClock.sleep(100)
            assertTrue("$description; foreground=${ui.rootInActiveWindow?.packageName}", predicate())
        }
        fun isSettings() = ui.rootInActiveWindow?.packageName == "com.android.settings"
        fun isHome() = ui.rootInActiveWindow?.packageName == app.packageName
        val settings = app.settingsRepository
        val original = runBlocking { CaptureStartPreference.initialize(app); settings.get() }
        val previousMode = requireNotNull(CaptureStartPreference.mode.value)
        val appOp = "cmd appops"
        val permission = "${app.packageName} SYSTEM_ALERT_WINDOW"
        val previousOp = Regex("""SYSTEM_ALERT_WINDOW:\s*([a-z_]+)""").find(shell("$appOp get $permission"))
            ?.groupValues?.get(1) ?: "default"
        val monitor = instrumentation.addMonitor(CaptureStartRequestActivity::class.java.name, null, false)
        try {
            assertTrue("Finish onboarding before testing the real home screen", OnboardingPrefs.isCompleted(app))
            shell("$appOp set $permission deny")
            assertFalse(Settings.canDrawOverlays(app))
            CaptureStartPreference.select(CaptureStartMode.SYSTEM)
            runBlocking { settings.update { it.copy(sourceLang = "en", targetLang = "ru",
                ocrEngine = OcrEngineKind.ML_KIT_LATIN, translatorEngine = TranslatorEngine.GOOGLE) } }
            val strings = AppLocalePrefs.wrap(app)
            val start = hasText(strings.getString(R.string.mobile_start)) and hasClickAction()
            val configure = hasText(strings.getString(R.string.mobile_configure)) and hasClickAction()
            ActivityScenario.launch(MainActivity::class.java).use { home ->
                compose.waitUntil(20_000) { compose.onAllNodes(start and isEnabled()).fetchSemanticsNodes().isNotEmpty() }
                compose.onNode(start).performClick()
                compose.onNode(configure).assertIsDisplayed()
                home.recreate()
                compose.onNode(configure).assertIsDisplayed().performClick()

                waitFor("System overlay settings opened") { isSettings() }
                shell("input keyevent KEYCODE_BACK")
                waitFor("Denial returned to the app") { isHome() }
                compose.onNode(start).assertIsDisplayed()
                assertFalse(Settings.canDrawOverlays(app))
                val completedStarts = monitor.hits
                assertEquals("The requested start must own its permission result", 1, completedStarts)

                // Open Settings independently, exactly as the permission checklist does.
                home.onActivity { openOverlayPermissionSettings(it) }
                waitFor("Separate visit to Settings") { isSettings() }
                shell("$appOp set $permission allow")
                shell("input keyevent KEYCODE_BACK")
                waitFor("New grant handed back to the home screen") { isHome() && Settings.canDrawOverlays(app) }
                compose.waitUntil(20_000) { compose.onAllNodesWithText(strings.getString(R.string.mobile_ready)).fetchSemanticsNodes().isNotEmpty() }
                assertEquals("An old start reappeared after an unrelated grant", completedStarts, monitor.hits)
                assertFalse(CaptureServiceState.running.value)

                compose.onNode(start).performClick()
                waitFor("A new tap requests capture") { monitor.hits == completedStarts + 1 }
                waitFor("MediaProjection asks for consent") { ui.rootInActiveWindow?.packageName == "com.android.systemui" }
                shell("input keyevent KEYCODE_BACK")
                waitFor("Declining screen capture returns home") { isHome() }
                assertFalse(CaptureServiceState.running.value)
            }
        } finally {
            instrumentation.removeMonitor(monitor)
            shell("$appOp set $permission $previousOp")
            CaptureStartPreference.select(previousMode)
            runBlocking { settings.update { it.copy(sourceLang = original.sourceLang, targetLang = original.targetLang,
                ocrEngine = original.ocrEngine, translatorEngine = original.translatorEngine) } }
        }
    }
}
