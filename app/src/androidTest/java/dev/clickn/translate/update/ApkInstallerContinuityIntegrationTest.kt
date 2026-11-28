package dev.clickn.translate.update

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.view.accessibility.AccessibilityWindowInfo
import androidx.core.content.pm.PackageInfoCompat
import androidx.lifecycle.Lifecycle
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.workDataOf
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.download.ModelDownloadSpec
import dev.clickn.translate.download.ModelDownloadWorkPolicy
import dev.clickn.translate.download.ModelDownloadWorker
import dev.clickn.translate.ui.MainActivity
import java.io.File
import java.security.MessageDigest
import java.util.UUID
import java.util.concurrent.TimeUnit
import java.util.zip.ZipFile
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** The acceptance runner uses its own debug key and two temporary APKs on its disposable AVD. */
@RunWith(AndroidJUnit4::class)
class ApkInstallerContinuityIntegrationTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val app get() = instrumentation.targetContext.applicationContext as ClickTranslateApp
    private val fixture get() = app.getSharedPreferences("qa_apk_install_continuity", Context.MODE_PRIVATE)
    private val work get() = WorkManager.getInstance(app)
    private val info get() = app.packageManager.getPackageInfo(app.packageName, 0)

    private fun phase(expected: String) =
        assumeTrue(InstrumentationRegistry.getArguments().getString("apkUpgradePhase") == expected)

    @Test fun sameSignedApkOpensAndroidInstallerAndCorruptCopyCannotStartIt() {
        phase("inspect")
        val directory = File(app.filesDir, "qa-apk-upgrade")
        val source = File(directory, "newer.apk")
        val version = requireNotNull(info.versionName)
        val code = PackageInfoCompat.getLongVersionCode(info)
        val digest = MessageDigest.getInstance("SHA-256")
        source.inputStream().buffered().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        val abi = ZipFile(source).use { zip ->
            zip.entries().asSequence().filter { it.name.startsWith("lib/") && it.name.endsWith(".so") }
                .map { it.name.split('/')[1] }.distinct().single()
        }
        assertTrue("The generated fixture must use an ABI actually supported by this AVD", abi in Build.SUPPORTED_ABIS)
        val apk = ReleaseApk("v$version", "ClicknTranslate-$version-$abi.apk", source.length(), digest.digest().hex(), code + 1)
        val ready = verifiedApkFile(app, apk)
        ready.parentFile!!.mkdirs()
        try {
            source.copyTo(ready, overwrite = true)
            ready.appendBytes(byteArrayOf(0))
            assertTrue("A changed APK must never reach the installer",
                runCatching { verifiedInstallerIntent(app, apk) }.exceptionOrNull() is InvalidApk)
            source.copyTo(ready, overwrite = true)
            val intent = verifiedInstallerIntent(app, apk)
            assertEquals(Intent.ACTION_VIEW, intent.action)
            assertEquals("application/vnd.android.package-archive", intent.type)
            assertEquals("content", intent.data?.scheme)
            assertEquals("${app.packageName}.logfileprovider", intent.data?.authority)
            assertTrue(intent.flags and Intent.FLAG_GRANT_READ_URI_PERMISSION != 0)

            val ui = instrumentation.uiAutomation
            val initialFlags = ui.serviceInfo.flags
            try {
                ui.serviceInfo = ui.serviceInfo.apply {
                    flags = flags or AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS
                }
                ActivityScenario.launch(MainActivity::class.java).use { scenario ->
                    scenario.onActivity { it.startActivity(intent) }
                    val deadline = SystemClock.elapsedRealtime() + 12_000
                    var found = false
                    while (!found && SystemClock.elapsedRealtime() < deadline) {
                        found = ui.windows.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
                            .mapNotNull { it.root }.any { root ->
                                val pkg = root.packageName?.toString().orEmpty()
                                (pkg.endsWith(".packageinstaller") || pkg.endsWith(".permissioncontroller")) &&
                                    listOf("Update", "Install").any { label ->
                                        root.findAccessibilityNodeInfosByText(label).any {
                                            it.text?.toString().equals(label, ignoreCase = true) && it.isClickable
                                        }
                                    }
                            }
                        if (!found) SystemClock.sleep(120)
                    }
                    assertTrue("Android's installer must offer the actual Update or Install action", found)
                    val frame = requireNotNull(ui.takeScreenshot())
                    try {
                        File(directory, "installer.png").outputStream().use { out ->
                            assertTrue(frame.compress(Bitmap.CompressFormat.PNG, 100, out))
                        }
                    } finally { frame.recycle() }
                    ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand("input keyevent KEYCODE_BACK")).use { it.readBytes() }
                }
            } finally { ui.serviceInfo = ui.serviceInfo.apply { flags = initialFlags } }
        } finally { ready.delete() }

        val previousAlpha = runBlocking { app.settingsRepository.get().overlayAlpha }
        val spec = ModelDownloadSpec.mlKitTranslation("fr", "de")
        val queued = OneTimeWorkRequestBuilder<ModelDownloadWorker>().setInitialDelay(1, TimeUnit.DAYS)
            .setInputData(workDataOf(ModelDownloadWorker.KEY_SPECS to arrayOf(spec.encode())))
            .addTag(ModelDownloadWorkPolicy.WORK_TAG).addTag(ModelDownloadWorkPolicy.specTag(spec)).build()
        work.enqueue(queued).result.get(10, TimeUnit.SECONDS)
        runBlocking { app.settingsRepository.update { it.copy(overlayAlpha = 0.57f) } }
        assertTrue(fixture.edit().putLong("firstInstall", info.firstInstallTime).putLong("currentCode", code)
            .putString("worker", queued.id.toString()).putFloat("previousAlpha", previousAlpha).commit())
    }

    @Test fun anInPlaceUpgradePreservesSettingsAndQueuedModelAndLaunchesTheRealApplication() {
        phase("recover")
        val id = UUID.fromString(requireNotNull(fixture.getString("worker", null)))
        try {
            assertEquals(fixture.getLong("currentCode", -1), PackageInfoCompat.getLongVersionCode(info))
            assertEquals("The app must be upgraded in place", fixture.getLong("firstInstall", -1), info.firstInstallTime)
            assertEquals(0.57f, runBlocking { app.settingsRepository.get().overlayAlpha }, 0.001f)
            assertEquals(WorkInfo.State.ENQUEUED, work.getWorkInfoById(id).get(10, TimeUnit.SECONDS)?.state)
            ActivityScenario.launch(MainActivity::class.java).use { assertEquals(Lifecycle.State.RESUMED, it.state) }
        } finally {
            work.cancelWorkById(id).result.get(10, TimeUnit.SECONDS)
            val original = fixture.getFloat("previousAlpha", 1f)
            runBlocking { app.settingsRepository.update { it.copy(overlayAlpha = original) } }
            fixture.edit().clear().commit()
        }
    }
}
