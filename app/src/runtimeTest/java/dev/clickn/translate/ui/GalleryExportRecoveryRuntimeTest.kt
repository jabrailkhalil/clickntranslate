package dev.clickn.translate.ui

import android.app.Application
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.R
import dev.clickn.translate.gallery.GalleryExportRecoveryStatus
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class, qualifiers = "en-rUS-w360dp-h800dp")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class GalleryExportRecoveryRuntimeTest {
    @get:Rule val compose = createComposeRule()
    private val context: Application get() = ApplicationProvider.getApplicationContext()

    @Test fun keepRequiresExplicitConfirmationAndDispatchesTheDisplayedSnapshotOnly() {
        var checks = 0
        val kept = mutableListOf<String>()
        val status = GalleryExportRecoveryStatus(pending = 1, unknownDestination = 1, reviewToken = "displayed-snapshot")
        compose.setContent {
            MaterialTheme { GalleryExportRecoveryNotice(status, false, false, { checks++ }, { kept += it }) }
        }
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_pending, 2)).assertIsDisplayed()
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_check)).performClick()
        compose.runOnIdle { assertEquals(1, checks); assertTrue(kept.isEmpty()) }

        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep)).performClick()
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep_message)).assertIsDisplayed()
        compose.runOnIdle { assertTrue(kept.isEmpty()) }
        compose.onNodeWithText(context.getString(android.R.string.cancel)).performClick()
        compose.onNode(isDialog()).assertDoesNotExist()
        compose.runOnIdle { assertTrue(kept.isEmpty()) }

        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep)).performClick()
        confirmKeep()
        compose.runOnIdle { assertEquals(listOf("displayed-snapshot"), kept) }
        compose.onNode(isDialog()).assertDoesNotExist()
    }

    @Test fun changedRecoverySnapshotDismissesOldConfirmationWithoutAcknowledgingNewExport() {
        val status = mutableStateOf(GalleryExportRecoveryStatus(pending = 1, reviewToken = "old"))
        val kept = mutableListOf<String>()
        compose.setContent {
            MaterialTheme { GalleryExportRecoveryNotice(status.value, false, false, {}, { kept += it }) }
        }
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep)).performClick()
        compose.onNode(isDialog()).assertIsDisplayed()
        compose.runOnIdle { status.value = GalleryExportRecoveryStatus(pending = 2, reviewToken = "new") }
        compose.onNode(isDialog()).assertDoesNotExist()
        compose.runOnIdle { assertTrue(kept.isEmpty()) }
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep)).performClick()
        confirmKeep()
        compose.runOnIdle { assertEquals(listOf("new"), kept) }
    }

    @Test fun cleanStateHidesTheBannerAndUnavailableOrBusyStateCannotDiscardRecords() {
        val status = mutableStateOf(GalleryExportRecoveryStatus())
        val busy = mutableStateOf(false)
        compose.setContent {
            MaterialTheme { GalleryExportRecoveryNotice(status.value, busy.value, false, {}, { error("Unexpected keep") }) }
        }
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_title)).assertDoesNotExist()
        compose.runOnIdle { status.value = GalleryExportRecoveryStatus(journalAvailable = false) }
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_unavailable)).assertIsDisplayed()
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep)).assertDoesNotExist()
        compose.runOnIdle {
            status.value = GalleryExportRecoveryStatus(pending = 1, reviewToken = "known")
            busy.value = true
        }
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_check)).assertIsNotEnabled()
        compose.onNodeWithText(context.getString(R.string.gallery_export_recovery_keep)).assertIsNotEnabled()
    }

    private fun confirmKeep() {
        compose.onNode(hasText(context.getString(R.string.gallery_export_recovery_keep_confirm)) and
            hasAnyAncestor(isDialog())).performClick()
    }
}
