package dev.clickn.translate.update

import android.content.Context
import android.content.Intent
import android.os.Process
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.workDataOf
import dev.clickn.translate.BuildConfig
import dev.clickn.translate.R
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.download.ModelDownloadSpec
import dev.clickn.translate.download.ModelDownloadWorkPolicy
import dev.clickn.translate.download.ModelDownloadWorker
import dev.clickn.translate.ui.MainActivity
import java.util.UUID
import java.util.concurrent.TimeUnit
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** The acceptance runner force-stops the target between these independent instrumentation calls. */
@RunWith(AndroidJUnit4::class)
class ColdDownloadQueueIntegrationTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val app get() = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext
    private val work get() = WorkManager.getInstance(app)
    private val fixture get() = app.getSharedPreferences("qa_cold_download_queue", Context.MODE_PRIVATE)
    private val updatePrefs get() = app.getSharedPreferences("update_checker", Context.MODE_PRIVATE)
    private val apk = ReleaseApk("v9.0.0", "ClicknTranslate-9.0.0-x64.apk", 8192, "c".repeat(64), 900)

    private fun phase(expected: String) =
        assumeTrue(InstrumentationRegistry.getArguments().getString("coldQueuePhase") == expected)

    private fun state(id: UUID): WorkInfo.State? = work.getWorkInfoById(id).get(5, TimeUnit.SECONDS)?.state

    private fun openSettings(check: (UpdateViewModel) -> Unit) {
        val intent = Intent(app, MainActivity::class.java)
            .putExtra(MainActivity.EXTRA_START_ROUTE, MainActivity.ROUTE_SETTINGS)
        ActivityScenario.launch<MainActivity>(intent).use { activity ->
            lateinit var updater: UpdateViewModel
            activity.onActivity { updater = ViewModelProvider(it)[UpdateViewModel::class.java] }
            val strings = AppLocalePrefs.wrap(app)
            val waiting = strings.getString(R.string.model_download_waiting)
            val pair = hasText("fr→de", substring = true)
            val arabic = hasText(strings.getString(R.string.settings_ocr_chip_tesseract_arabic), substring = true) and
                hasText(waiting, substring = true)
            compose.waitUntil(15_000) { compose.onAllNodes(pair).fetchSemanticsNodes().isNotEmpty() }
            compose.onNode(pair).assertIsDisplayed()
            compose.onNode(arabic).assertIsDisplayed()
            compose.waitUntil(10_000) { (updater.transfer.value as? UpdateViewModel.State.Downloading)?.apk == apk }
            check(updater)
        }
    }

    @Test fun stagePersistentWorkAndCloseSettings() {
        phase("stage")
        assertNull("The dedicated emulator must have no pending APK download", updatePrefs.getString("apk_job", null))
        fun pending(spec: ModelDownloadSpec) = OneTimeWorkRequestBuilder<ModelDownloadWorker>()
            .setInitialDelay(1, TimeUnit.DAYS)
            .setInputData(workDataOf(ModelDownloadWorker.KEY_SPECS to arrayOf(spec.encode())))
            .addTag(ModelDownloadWorkPolicy.WORK_TAG).addTag(ModelDownloadWorkPolicy.specTag(spec)).build()
        val pair = pending(ModelDownloadSpec.mlKitTranslation("fr", "de"))
        val arabic = pending(ModelDownloadSpec.tesseractArabic())
        val update = OneTimeWorkRequestBuilder<ApkUpdateWorker>().setInitialDelay(1, TimeUnit.DAYS)
            .setInputData(workDataOf(ApkUpdateWorker.APK to Json.encodeToString(apk))).build()
        val record = buildJsonObject {
            put("id", update.id.toString())
            put("apk", Json.encodeToJsonElement(ReleaseApk.serializer(), apk))
            put("installedCode", BuildConfig.VERSION_CODE)
        }
        assertTrue(fixture.edit().putInt("pid", Process.myPid()).putLong("start", Process.getStartElapsedRealtime())
            .putString("pair", pair.id.toString()).putString("arabic", arabic.id.toString())
            .putString("apk", update.id.toString()).commit())
        work.enqueue(listOf(pair, arabic)).result.get(10, TimeUnit.SECONDS)
        work.enqueueUniqueWork(ApkUpdateWorker.WORK_NAME, ExistingWorkPolicy.KEEP, update).result.get(10, TimeUnit.SECONDS)
        assertTrue(updatePrefs.edit().putString("apk_job", record.toString()).commit())
        openSettings { updater ->
            compose.runOnIdle { updater.reset() }
            assertEquals(UpdateViewModel.State.Idle, updater.state.value)
            assertEquals(apk, (updater.transfer.value as UpdateViewModel.State.Downloading).apk)
        }
        listOf(pair.id, arabic.id, update.id).forEach { assertEquals(WorkInfo.State.ENQUEUED, state(it)) }
    }

    @Test fun sameQueueSurvivesProcessDeathAndCancellingAnApkKeepsBothModels() {
        phase("recover")
        fun id(name: String) = UUID.fromString(requireNotNull(fixture.getString(name, null)))
        val pair = id("pair")
        val arabic = id("arabic")
        val update = id("apk")
        try {
            assertTrue("Recovery must run in a new Android process", fixture.getInt("pid", -1) != Process.myPid() ||
                fixture.getLong("start", -1) != Process.getStartElapsedRealtime())
            listOf(pair, arabic, update).forEach { assertEquals(WorkInfo.State.ENQUEUED, state(it)) }
            openSettings { updater ->
                compose.runOnIdle { updater.cancelDownload() }
                compose.waitUntil(15_000) { updater.transfer.value == null && state(update) == WorkInfo.State.CANCELLED }
                assertNull(updatePrefs.getString("apk_job", null))
            }
            assertEquals(WorkInfo.State.ENQUEUED, state(pair))
            assertEquals(WorkInfo.State.ENQUEUED, state(arabic))
        } finally {
            listOf(pair, arabic, update).forEach { work.cancelWorkById(it).result.get(10, TimeUnit.SECONDS) }
            fixture.edit().clear().commit()
        }
    }
}
