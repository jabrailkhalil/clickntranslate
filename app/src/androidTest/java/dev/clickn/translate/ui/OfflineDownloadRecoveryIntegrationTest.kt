package dev.clickn.translate.ui

import android.content.Intent
import android.graphics.Bitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.workDataOf
import dev.clickn.translate.R
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.download.ModelDownloadSpec
import dev.clickn.translate.download.ModelDownloadWorkPolicy
import dev.clickn.translate.download.ModelDownloadWorker
import java.io.File
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineDownloadRecoveryIntegrationTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun coldLibraryAndRotationRecoverTheQueuedPairAndCancelOnlyItsWorkId() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("offlineRecovery") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val app = instrumentation.targetContext.applicationContext
        val strings = AppLocalePrefs.wrap(app)
        val scheduler = WorkManager.getInstance(app)
        fun pending(spec: ModelDownloadSpec) = OneTimeWorkRequestBuilder<ModelDownloadWorker>()
            .setInitialDelay(1, TimeUnit.DAYS)
            .setInputData(workDataOf(ModelDownloadWorker.KEY_SPECS to arrayOf(spec.encode())))
            .addTag(ModelDownloadWorkPolicy.WORK_TAG).addTag(ModelDownloadWorkPolicy.specTag(spec)).build()
        val pair = pending(ModelDownloadSpec.mlKitTranslation("fr", "de"))
        val unrelated = pending(ModelDownloadSpec.tesseractArabic())
        val row = hasTestTag("translation-download-${pair.id}")
        val download = hasTestTag("offline-pair-apply")
        val cancel = hasText(strings.getString(R.string.model_download_cancel)) and hasClickAction() and hasAnyAncestor(row)
        val ok = hasText(strings.getString(R.string.model_download_cancel_confirm_ok)) and hasClickAction()
        fun checkGlobalSettings(expectPair: Boolean) {
            val intent = Intent(app, MainActivity::class.java)
                .putExtra(MainActivity.EXTRA_START_ROUTE, MainActivity.ROUTE_SETTINGS)
            ActivityScenario.launch<MainActivity>(intent).use {
                val header = hasText(strings.getString(R.string.model_download_in_app_title))
                val expected = if (expectPair) 2 else 1
                compose.waitUntil(20_000) { compose.onAllNodes(header).fetchSemanticsNodes().size == expected }
                repeat(expected) { index -> compose.onAllNodes(header)[index].assertIsDisplayed() }
                val pairName = compose.onNode(hasText("fr→de", substring = true))
                if (expectPair) pairName.assertIsDisplayed() else pairName.assertDoesNotExist()
                compose.onNode(hasText(strings.getString(R.string.settings_ocr_chip_tesseract_arabic), substring = true)
                    and hasText(strings.getString(R.string.model_download_waiting), substring = true)).assertIsDisplayed()
            }
        }
        fun openLibrary() {
            val tab = hasText(strings.getString(R.string.mobile_nav_settings)) and hasClickAction()
            compose.waitUntil(20_000) { compose.onAllNodes(tab).fetchSemanticsNodes().isNotEmpty() }
            compose.onNode(tab).performClick()
            val library = hasText(strings.getString(R.string.refine_offline)) and hasClickAction()
            compose.onNodeWithTag("settings-hub").performScrollToNode(library)
            compose.onNode(library).performClick()
            compose.onNodeWithTag("offline-library").performScrollToNode(download)
            compose.onNode(download).assertIsNotEnabled()
            compose.onNodeWithTag("offline-library").performScrollToNode(row)
            compose.onNode(row).assertIsDisplayed()
            compose.onNodeWithTag("offline-library").performScrollToNode(cancel)
            compose.onNode(cancel).assertIsDisplayed()
        }
        try {
            scheduler.enqueue(listOf(pair, unrelated)).result.get(10, TimeUnit.SECONDS)
            checkGlobalSettings(expectPair = true)
            ActivityScenario.launch(MainActivity::class.java).use { openLibrary() }
            assertEquals(WorkInfo.State.ENQUEUED, scheduler.getWorkInfoById(pair.id).get(10, TimeUnit.SECONDS)?.state)
            ActivityScenario.launch(MainActivity::class.java).use { home ->
                openLibrary()
                val screen = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
                try {
                    File(app.filesDir, "qa-offline-queued-pair.png").outputStream().use { stream ->
                        assertTrue(screen.compress(Bitmap.CompressFormat.PNG, 100, stream))
                    }
                } finally { screen.recycle() }
                compose.onNode(cancel).performTouchInput { click() }
                compose.onNode(ok).assertIsDisplayed()
                home.recreate()
                compose.waitUntil(15_000) { compose.onAllNodes(ok).fetchSemanticsNodes().isNotEmpty() }
                compose.onNode(ok).assertIsDisplayed().performTouchInput { click() }
                compose.waitUntil(10_000) {
                    scheduler.getWorkInfoById(pair.id).get(2, TimeUnit.SECONDS)?.state == WorkInfo.State.CANCELLED
                }
                assertEquals("The unrelated download must retain its own work",
                    WorkInfo.State.ENQUEUED, scheduler.getWorkInfoById(unrelated.id).get(10, TimeUnit.SECONDS)?.state)
                compose.onNodeWithTag("offline-library").performScrollToNode(download)
                compose.onNode(download).assertIsEnabled()
            }
            checkGlobalSettings(expectPair = false)
        } finally {
            scheduler.cancelWorkById(pair.id).result.get(10, TimeUnit.SECONDS)
            scheduler.cancelWorkById(unrelated.id).result.get(10, TimeUnit.SECONDS)
        }
    }
}
