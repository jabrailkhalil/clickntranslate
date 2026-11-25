package dev.clickn.translate.capture

import android.accessibilityservice.AccessibilityServiceInfo
import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionConfig
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.provider.Settings
import android.view.Display
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.view.accessibility.AccessibilityNodeInfo
import android.view.inspector.WindowInspector
import android.widget.TextView
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureServiceState
import dev.clickn.translate.ui.MainActivity
import java.net.InetAddress
import java.util.concurrent.CompletableFuture
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import timber.log.Timber

/** Uses a real SystemUI grant. Opt in only on a freshly provisioned, unlocked Google API 35 AVD. */
@RunWith(AndroidJUnit4::class)
class MediaProjectionConsentIntegrationTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val ui get() = instrumentation.uiAutomation
    private val frames = AtomicInteger()
    private val phrases = mapOf("Blue door" to "Синяя дверь", "Green door" to "Зелёная дверь")
    private val recognized = ConcurrentHashMap.newKeySet<String>()
    private val frameObserver = object : Timber.Tree() {
        override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
            // Emitted after the production screenshotter converts an ImageReader image to a bitmap.
            if (tag == "VerticalDiag" && message.startsWith("mediaProjection frame image=")) {
                frames.incrementAndGet()
            }
        }
    }

    @Test fun denyThenGrantSystemRevokeAndRestart() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("projectionConsent") == "true")
        assertEquals("This fixture uses the API 35 SystemUI consent dialog", 35, Build.VERSION.SDK_INT)
        assertTrue("Use a disposable AVD", Build.HARDWARE == "ranchu" || Build.HARDWARE == "goldfish")
        assertFalse("The AVD already has an active recording", shell("dumpsys media_projection").contains(", uid="))
        assertTrue("The app must start with no capture resources", appCaptureReleased())
        val opMode = Regex("""SYSTEM_ALERT_WINDOW:\s*([a-z_]+)""")
            .find(shell("cmd appops get ${context.packageName} SYSTEM_ALERT_WINDOW"))?.groupValues?.get(1) ?: "default"
        val restoreOverlay = !Settings.canDrawOverlays(context)
        val oldFlags = ui.serviceInfo.flags
        val peer = CompletableFuture<MediaProjection>()
        var peerLauncher: ActivityResultLauncher<Intent>? = null
        val settings = (context.applicationContext as ClickTranslateApp).settingsRepository
        val previous = runBlocking { settings.get() }
        val translator = MockWebServer()
        translator.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.method != "POST" || request.path != "/translate") return MockResponse().setResponseCode(404)
                val body = JSONObject(request.body.readUtf8())
                if (body.optString("source") != "en" || body.optString("target") != "ru") return MockResponse().setResponseCode(400)
                val text = body.getString("q").replace(Regex("\\s+"), " ")
                val match = phrases.entries.firstOrNull { text.contains(it.key, ignoreCase = true) }
                if (match != null) recognized.add(match.key)
                return MockResponse().setHeader("Content-Type", "application/json")
                    .setBody(JSONObject().put("translatedText", match?.value ?: text).toString())
            }
        }
        translator.start(InetAddress.getByName("127.0.0.1"), 0)
        Timber.plant(frameObserver)
        try {
            ui.serviceInfo = ui.serviceInfo.apply { flags = flags or AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS }
            if (restoreOverlay) shell("cmd appops set ${context.packageName} SYSTEM_ALERT_WINDOW allow")
            waitFor("overlay app-op") { Settings.canDrawOverlays(context) }
            runBlocking {
                settings.update { it.copy(
                    ocrEngine = OcrEngineKind.ML_KIT_LATIN, sourceLang = "en", targetLang = "ru",
                    translatorEngine = TranslatorEngine.LIBRETRANSLATE, libreTranslateApiKey = "",
                    libreTranslateBaseUrl = "http://127.0.0.1:${translator.port}", renderMode = RenderMode.FLOATING_WINDOW,
                ) }
            }

            ActivityScenario.launch(MainActivity::class.java).use { home ->
                home.onActivity { it.startActivity(CaptureStartRequestActivity.newIntent(it)) }
                chooseConsent(grant = false)
                waitFor("denial returns to the app") { appInFront() && appCaptureReleased() }
                assertFalse("Denial registered a system projection", ownsProjection())

                val firstDisplay = grantAndTranslate(home, "Blue door")

                // A second grant goes directly to Android, without calling the production stop action.
                // Android must revoke the first projection when it starts this separate, consented token.
                shell("input keyevent KEYCODE_BACK")
                waitFor("return from Android Settings") { appInFront() }
                home.onActivity { activity ->
                    val manager = requireNotNull(activity.getSystemService(MediaProjectionManager::class.java))
                    peerLauncher = activity.activityResultRegistry.register(
                        "qa-independent-projection", ActivityResultContracts.StartActivityForResult(),
                    ) { result ->
                        try {
                            check(result.resultCode == Activity.RESULT_OK) { "Independent consent was denied" }
                            peer.complete(requireNotNull(manager.getMediaProjection(result.resultCode, requireNotNull(result.data))))
                        } catch (failure: Exception) {
                            peer.completeExceptionally(failure)
                        }
                    }
                    peerLauncher!!.launch(manager.createScreenCaptureIntent(MediaProjectionConfig.createConfigForDefaultDisplay()))
                }
                chooseConsent(grant = true)
                val competingProjection = peer.get(25, TimeUnit.SECONDS)
                waitFor("Android revokes the old capture and the service releases its resources") { appCaptureReleased() }
                // Only after observing the application's termination may the test retire its own token.
                competingProjection.stop()
                waitFor("system projection grant cleared") { !ownsProjection() }

                val restartedDisplay = grantAndTranslate(home, "Green door")
                assertNotEquals("Restart reused the old display", firstDisplay, restartedDisplay)
                context.startService(CaptureService.stopIntent(context))
                waitFor("normal stop outside the app removes service, display, thread, windows and grant") {
                    appCaptureReleased() && !ownsProjection()
                }
            }
        } finally {
            instrumentation.runOnMainSync { peerLauncher?.unregister() }
            if (peer.isDone && !peer.isCompletedExceptionally) peer.getNow(null)?.stop()
            context.stopService(Intent(context, CaptureService::class.java))
            Timber.uproot(frameObserver)
            translator.shutdown()
            runBlocking {
                settings.update { it.copy(
                    ocrEngine = previous.ocrEngine, sourceLang = previous.sourceLang, targetLang = previous.targetLang,
                    translatorEngine = previous.translatorEngine, libreTranslateApiKey = previous.libreTranslateApiKey,
                    libreTranslateBaseUrl = previous.libreTranslateBaseUrl, renderMode = previous.renderMode,
                ) }
            }
            if (restoreOverlay) shell("cmd appops set ${context.packageName} SYSTEM_ALERT_WINDOW $opMode")
            ui.serviceInfo = ui.serviceInfo.apply { flags = oldFlags }
        }
    }

    private fun grantAndTranslate(home: ActivityScenario<MainActivity>, source: String): Int {
        home.onActivity { it.startActivity(CaptureStartRequestActivity.newIntent(it)) }
        chooseConsent(grant = true)
        waitFor("running capture, virtual display and Android projection grant") {
            CaptureServiceState.running.value && serviceRunning() && captureDisplays().size == 1 && ownsProjection()
        }
        val id = captureDisplays().single()
        home.onActivity { it.startActivity(Intent(Settings.ACTION_SETTINGS)) }
        waitFor("floating capture control over Android Settings") {
            ui.rootInActiveWindow?.packageName?.toString() == "com.android.settings" && overlayCount() > 0
        }
        withSourceCard(source) {
            val before = frames.get()
            context.startService(Intent(context, CaptureService::class.java).setAction(CaptureService.ACTION_TRIGGER_ONCE))
            waitFor("a fresh bitmap from the real screen capture action") { frames.get() > before }
            waitFor("local ML Kit reads '$source' and sends it to the loopback translator", 60_000) {
                source in recognized
            }
            val translated = phrases.getValue(source)
            waitFor("the real floating window shows '$translated'") {
                var shown = false
                instrumentation.runOnMainSync {
                    shown = WindowInspector.getGlobalWindowViews().any { hasVisibleText(it, translated) }
                }
                shown
            }
        }
        return id
    }

    // A controlled source drawn on Android's real display, separate from the app's floating controls.
    private fun withSourceCard(text: String, action: () -> Unit) {
        val display = requireNotNull(context.getSystemService(DisplayManager::class.java)?.getDisplay(Display.DEFAULT_DISPLAY))
        val windowContext = context.createDisplayContext(display)
            .createWindowContext(WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null)
        val windows = requireNotNull(windowContext.getSystemService(WindowManager::class.java))
        val drawn = CountDownLatch(1)
        lateinit var label: TextView
        instrumentation.runOnMainSync {
            label = TextView(windowContext).apply {
                this.text = text
                textSize = 42f
                gravity = Gravity.CENTER
                setTextColor(Color.BLACK)
                setBackgroundColor(Color.WHITE)
                viewTreeObserver.addOnDrawListener { drawn.countDown() }
            }
            windows.addView(label, WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE,
                PixelFormat.OPAQUE,
            ))
        }
        try {
            assertTrue("Test text did not draw on the display", drawn.await(10, TimeUnit.SECONDS))
            action()
        } finally {
            instrumentation.runOnMainSync { windows.removeViewImmediate(label) }
        }
    }

    private fun hasVisibleText(view: View, text: String): Boolean {
        if (!view.isShown) return false
        if (view is TextView && view.text?.contains(text) == true) return true
        return view is ViewGroup && (0 until view.childCount).any { hasVisibleText(view.getChildAt(it), text) }
    }

    private fun chooseConsent(grant: Boolean) {
        waitFor("system projection consent") {
            val root = ui.rootInActiveWindow ?: return@waitFor false
            if (root.packageName?.toString() != "com.android.systemui") return@waitFor false
            val positive = root.findAccessibilityNodeInfosByViewId("android:id/button1").firstOrNull()
            val negative = root.findAccessibilityNodeInfosByViewId("android:id/button2").firstOrNull()
            if (positive == null || negative == null) return@waitFor false
            val target = if (grant) positive else negative
            target.isVisibleToUser && target.isEnabled && target.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        }
    }

    private fun appInFront() = ui.rootInActiveWindow?.packageName?.toString() == context.packageName

    private fun ownsProjection() = shell("dumpsys media_projection").contains("(${context.packageName}, uid=")

    private fun captureDisplays() = requireNotNull(context.getSystemService(DisplayManager::class.java)).displays
        .filter { it.name == "Click'n'Translate截屏" }.map { it.displayId }

    @Suppress("DEPRECATION") // Android still reports this app's own running services.
    private fun serviceRunning() = requireNotNull(context.getSystemService(ActivityManager::class.java))
        .getRunningServices(Int.MAX_VALUE).any { it.service.className == CaptureService::class.java.name }

    private fun captureWorkerAlive() = Thread.getAllStackTraces().keys.any { it.isAlive && it.name == "MediaProjection-Capture" }

    private fun overlayCount(): Int {
        var count = 0
        instrumentation.runOnMainSync {
            count = WindowInspector.getGlobalWindowViews().count {
                it.isAttachedToWindow && (it.layoutParams as? WindowManager.LayoutParams)?.type ==
                    WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            }
        }
        return count
    }

    private fun appCaptureReleased() = !CaptureServiceState.running.value && captureDisplays().isEmpty() &&
        !serviceRunning() && !captureWorkerAlive() && overlayCount() == 0

    private fun waitFor(label: String, timeoutMs: Long = 25_000L, condition: () -> Boolean) {
        val deadline = SystemClock.elapsedRealtime() + timeoutMs
        do {
            if (condition()) return
            SystemClock.sleep(150)
        } while (SystemClock.elapsedRealtime() < deadline)
        val root = ui.rootInActiveWindow
        val buttons = listOf("button1", "button2").map { id ->
            root?.findAccessibilityNodeInfosByViewId("android:id/$id")?.map { it.text }
        }
        throw AssertionError(
            "$label timed out. Foreground=${root?.packageName}, buttons=$buttons, service=${serviceRunning()}, " +
                "running=${CaptureServiceState.running.value}, displays=${captureDisplays()}, worker=${captureWorkerAlive()}, " +
                "overlays=${overlayCount()}, frames=${frames.get()}, ${shell("dumpsys media_projection").trim()}",
        )
    }

    private fun shell(command: String): String =
        ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand(command)).bufferedReader().use { it.readText() }
}
