package dev.clickn.translate.ui

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.SettingsImportRecoveryState
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

/** Actual Main composition must not expose normal actions before recovery finishes. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "en-rUS")
@LooperMode(LooperMode.Mode.PAUSED)
class SettingsRecoveryRuntimeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun failedRecoveryCoversAppAndItsRealRetryReopensTheNormalScreen() {
        val gate = compose.activity.settingsImportRecoveryGate
        compose.onNodeWithTag("setup-next").assertIsDisplayed()
        compose.runOnIdle { gate.requireRecovery() }
        compose.onNodeWithTag("settings-recovery").assertIsDisplayed()
        compose.onNodeWithText(compose.activity.getString(R.string.settings_import_recovery_failed)).assertIsDisplayed()
        compose.onNodeWithTag("setup-next").assertDoesNotExist()
        // The application's actual IO recovery callback runs; no terminal state is injected.
        compose.onNodeWithText(compose.activity.getString(R.string.settings_import_recovery_retry)).performClick()
        compose.waitUntil(10_000) { gate.state.value == SettingsImportRecoveryState.READY }
        compose.waitForIdle()
        compose.onNodeWithTag("settings-recovery").assertDoesNotExist()
        compose.onNodeWithTag("setup-next").assertIsDisplayed()
    }

    @Test fun pendingRecoveryKeepsAppHiddenUntilTheRecoveryOperationReallyCompletes() {
        val gate = compose.activity.settingsImportRecoveryGate
        val release = CompletableDeferred<Unit>()
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        try {
            compose.runOnIdle {
                gate.start(scope) { release.await() }
                gate.requireRecovery()
                gate.retry()
            }
            assertEquals(SettingsImportRecoveryState.RECOVERING, gate.state.value)
            compose.onNodeWithTag("settings-recovery").assertIsDisplayed()
            compose.onNodeWithText(compose.activity.getString(R.string.settings_import_recovering)).assertIsDisplayed()
            compose.onNodeWithTag("setup-next").assertDoesNotExist()
            compose.onNodeWithText(compose.activity.getString(R.string.settings_import_recovery_retry)).assertDoesNotExist()
            compose.runOnIdle { release.complete(Unit) }
            compose.waitUntil(10_000) { gate.state.value == SettingsImportRecoveryState.READY }
            compose.waitForIdle()
            compose.onNodeWithTag("settings-recovery").assertDoesNotExist()
            compose.onNodeWithTag("setup-next").assertIsDisplayed()
        } finally {
            release.complete(Unit)
            scope.cancel()
        }
    }
}
