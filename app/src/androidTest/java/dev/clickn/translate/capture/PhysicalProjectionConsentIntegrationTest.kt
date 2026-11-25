package dev.clickn.translate.capture

import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.graphics.Point
import android.graphics.Rect
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.Bundle
import android.os.ParcelFileDescriptor
import android.os.SystemClock
import android.os.UserManager
import android.provider.Settings
import android.view.Display
import android.view.View
import android.view.ViewGroup
import android.view.accessibility.AccessibilityNodeInfo
import android.view.inspector.WindowInspector
import android.widget.TextView
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.runner.lifecycle.ActivityLifecycleMonitorRegistry
import androidx.test.runner.lifecycle.Stage
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.OcrEngineKind
import dev.clickn.translate.data.RenderMode
import dev.clickn.translate.data.TranslatorEngine
import dev.clickn.translate.service.CaptureService
import dev.clickn.translate.service.CaptureServiceState
import dev.clickn.translate.trigger.AccessibilityServiceStatus
import dev.clickn.translate.ui.MainActivity
import java.net.InetAddress
import java.util.concurrent.CountDownLatch
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import timber.log.Timber

/** Physical-device projections on a disposable foreground user. Neither probe saves a screen or UI dump. */
@RunWith(AndroidJUnit4::class)
class PhysicalProjectionConsentIntegrationTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val ui get() = instrumentation.uiAutomation
    private var user = -1
    private val fixture = "dev.clickn.qa.page"
    private val fixtureLabel = "CT QA card"
    private var selectorStep = "not started"
    private val metrics = CaptureMetrics()

    @Test fun taskOnlyDenyGrantRevokeWhileTranslatingAndRestart() = runPhysical(defaultDisplay = false)
    @Test fun defaultDisplayTranslatesTheOwnedCardAndStops() = runPhysical(defaultDisplay = true)

    private fun runPhysical(defaultDisplay: Boolean) {
        val args = InstrumentationRegistry.getArguments()
        val flag = if (defaultDisplay) "physicalDefaultProjectionConsent" else "physicalProjectionConsent"
        assumeTrue("Opt in on a disposable physical QA profile", args.getString(flag) == "true")
        user = requireNotNull(args.getString("qaUser")?.toIntOrNull()).also { require(it > 0) }
        assertTrue(Build.VERSION.SDK_INT >= 34)
        assertTrue("Instrumentation must belong to the foreground QA user",
            requireNotNull(context.getSystemService(UserManager::class.java)).isUserForeground)
        ensureQaForeground()
        assertTrue("Expected the dedicated ClicknTranslateQA-46 profile",
            shell("pm list users").contains("UserInfo{$user:ClicknTranslateQA-46:"))
        assertTrue("Install the no-permission CT QA card fixture for this user", shell("pm path --user $user $fixture").startsWith("package:"))
        assertTrue("Allow overlays for the target app in the disposable QA user", Settings.canDrawOverlays(context))
        assertFalse("Accessibility capture must be off to test MediaProjection", AccessibilityServiceStatus.isEnabled(context))
        assertTrue("Close the existing app capture first", released())
        assertEquals("Close any existing device recording before the QA grant", ProjectionOwner.NONE, projectionOwner())

        val incomingBlue = CountDownLatch(1)
        val allowBlueReply = CountDownLatch(1)
        val sentBlueReply = CountDownLatch(1)
        val incomingGreen = CountDownLatch(1)
        val server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                if (request.path != "/translate" || request.method != "POST") return MockResponse().setResponseCode(404)
                val data = JSONObject(request.body.readUtf8())
                metrics["lastPostKind"] = metrics.kind(data.optString("q"))
                metrics["lastPostLength"] = data.optString("q").length.toString()
                if (data.optString("source") != "en" || data.optString("target") != "ru") return MockResponse().setResponseCode(400)
                val answer = when (data.optString("q").trim()) {
                    "Blue door" -> {
                        incomingBlue.countDown()
                        if (!allowBlueReply.await(80, TimeUnit.SECONDS)) return MockResponse().setResponseCode(504)
                        sentBlueReply.countDown()
                        "Синяя дверь"
                    }
                    "Green door" -> { incomingGreen.countDown(); "Зелёная дверь" }
                    else -> return MockResponse().setResponseCode(400)
                }
                return MockResponse().setHeader("Content-Type", "application/json")
                    .setBody(JSONObject().put("translatedText", answer).toString())
            }
        }
        val settings = (context.applicationContext as ClickTranslateApp).settingsRepository
        val previous = runBlocking { settings.get() }
        runBlocking { CaptureStartPreference.initialize(context) }
        val priorBackend = requireNotNull(CaptureStartPreference.mode.value)
        val originalFlags = ui.serviceInfo.flags
        server.start(InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)), 0)
        Timber.plant(metrics)
        try {
            ui.serviceInfo = ui.serviceInfo.apply { flags = originalFlags or AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                AccessibilityServiceInfo.FLAG_RETRIEVE_INTERACTIVE_WINDOWS }
            CaptureStartPreference.select(CaptureStartMode.SYSTEM)
            assertTrue(runBlocking { CaptureStartPreference.awaitPersistence() })
            val crop = if (defaultDisplay) {
                showPage("green")
                fixtureCrop()
            } else null
            crop?.let { (area, pixels) ->
                metrics["fixtureDisplay"] = "${pixels.x}x${pixels.y}"
                metrics["requestedCrop"] = "${area.left},${area.top},${area.right},${area.bottom}"
            }
            runBlocking { settings.update { it.copy(
                developerOptionsEnabled = !defaultDisplay, shareEntireScreen = false,
                sourceLang = "en", targetLang = "ru", ocrEngine = OcrEngineKind.ML_KIT_LATIN,
                translatorEngine = TranslatorEngine.LIBRETRANSLATE, libreTranslateApiKey = "",
                libreTranslateBaseUrl = "http://127.0.0.1:${server.port}", apiTimeoutSeconds = 120,
                renderMode = RenderMode.FLOATING_WINDOW,
                captureRegion = crop?.first, captureRegionSavedScreenW = crop?.second?.x ?: 0,
                captureRegionSavedScreenH = crop?.second?.y ?: 0, captureRegionBorderEnabled = false,
                ocrScreenshotSavingEnabled = false, disableTranslationCache = true,
            ) } }

            if (crop != null) {
                assertTrue(shouldRequestEntireScreen(Build.VERSION.SDK_INT, false, false))
                assertFixtureInFront(crop.first)
                context.startActivity(CaptureStartRequestActivity.newIntent(context))
                confirmDefaultDisplay()
                waitFor("default system grant and virtual display") { running() }
                val display = displays().single()
                showPage("green")
                val elapsed = checkGreenAndStop(incomingGreen, crop.first)
                assertEquals("Only the owned green card may be sent to the loopback server", 1, server.requestCount)
                instrumentation.addResults(Bundle().apply {
                    putString("physicalDefaultProjection",
                        "scope=default_display display=$display knownRequests=1 greenRendered=true greenMs=$elapsed")
                    putString("physicalProjectionMetrics", metrics.summary())
                })
                return
            }
            showPage("blue")
            openRequest()
            chooseTaskConsent(grant = false)
            waitFor("denied consent returns to the app") { ui.rootInActiveWindow?.packageName == context.packageName && released() }
            assertEquals(ProjectionOwner.NONE, projectionOwner())
            openRequest()
            chooseTaskConsent(grant = true)
            waitFor("first system grant and virtual display") { running() }
            val firstDisplay = displays().single()
            showPage("blue")
            trigger()
            assertTrue("The captured synthetic blue card did not reach the adapter", incomingBlue.await(50, TimeUnit.SECONDS))
            assertEquals(1L, allowBlueReply.count)
            // Long-click the recorded fixture's own view. It finishes only its own task; Android
            // then stops app-only sharing with STOP_TARGET_REMOVED, without a stop call to our app.
            waitFor("finish the recorded QA task through its view") {
                qaCardNode("Blue door")?.performAction(AccessibilityNodeInfo.ACTION_LONG_CLICK) == true
            }
            waitFor("OS revokes the removed task and releases the app's capture resources") {
                released() && projectionOwner() == ProjectionOwner.NONE
            }
            allowBlueReply.countDown()
            assertTrue(sentBlueReply.await(5, TimeUnit.SECONDS))
            val quietUntil = SystemClock.elapsedRealtime() + 1_250L
            while (SystemClock.elapsedRealtime() < quietUntil) {
                assertTrue(released())
                assertFalse(hasResult("Синяя дверь"))
                SystemClock.sleep(100)
            }
            showPage("green")
            openRequest()
            chooseTaskConsent(grant = true)
            waitFor("a fresh system capture after recorded task removal") { running() }
            val restartDisplay = displays().single()
            assertNotEquals(firstDisplay, restartDisplay)
            showPage("green")
            val elapsed = checkGreenAndStop(incomingGreen)
            instrumentation.addResults(Bundle().apply { putString("physicalProjection",
                "scope=selected_task firstDisplay=$firstDisplay restartDisplay=$restartDisplay bluePending=true greenRendered=true greenMs=$elapsed") })
        } catch (error: Throwable) {
            val detail = "requests=${server.requestCount} owner=${projectionOwner()} " +
                "running=${CaptureServiceState.running.value} displays=${displays()} metrics=${metrics.summary()}"
            instrumentation.addResults(Bundle().apply { putString("physicalProjectionDiagnostic", detail) })
            throw AssertionError("${error.message}; $detail", error)
        } finally {
            allowBlueReply.countDown()
            context.stopService(Intent(context, CaptureService::class.java))
            server.shutdown()
            Timber.uproot(metrics)
            runBlocking { settings.update { it.copy(
                developerOptionsEnabled = previous.developerOptionsEnabled, shareEntireScreen = previous.shareEntireScreen,
                sourceLang = previous.sourceLang, targetLang = previous.targetLang, ocrEngine = previous.ocrEngine,
                translatorEngine = previous.translatorEngine, libreTranslateApiKey = previous.libreTranslateApiKey,
                libreTranslateBaseUrl = previous.libreTranslateBaseUrl, apiTimeoutSeconds = previous.apiTimeoutSeconds,
                renderMode = previous.renderMode,
                captureRegion = previous.captureRegion, captureRegionSavedScreenW = previous.captureRegionSavedScreenW,
                captureRegionSavedScreenH = previous.captureRegionSavedScreenH, captureRegionBorderEnabled = previous.captureRegionBorderEnabled,
                ocrScreenshotSavingEnabled = previous.ocrScreenshotSavingEnabled, disableTranslationCache = previous.disableTranslationCache,
            ) } }
            CaptureStartPreference.select(priorBackend)
            runBlocking { CaptureStartPreference.awaitPersistence() }
            ui.serviceInfo = ui.serviceInfo.apply { flags = originalFlags }
        }
    }

    @Suppress("DEPRECATION") // Match the default display's physical pixel coordinate system.
    private fun fixtureCrop(): Pair<CaptureRegion, Point> {
        val text = requireNotNull(qaCardNode("Green door"))
        val card = Rect().also(text::getBoundsInScreen)
        val dm = requireNotNull(context.getSystemService(DisplayManager::class.java))
        val pixels = Point().also(requireNotNull(dm.getDisplay(Display.DEFAULT_DISPLAY))::getRealSize)
        // At 560 dpi this owned 48sp phrase spans 828px of a 1272px card.
        // Keep the full line inside the crop, with a small inset from the card edges.
        val x = card.width() / 24
        val y = card.height() * 2 / 5
        val area = CaptureRegion(card.left + x, card.top + y, card.right - x, card.bottom - y)
        check(area.isValid() && area.left >= 0 && area.top >= 0 && area.right <= pixels.x && area.bottom <= pixels.y)
        return area to pixels
    }

    private fun assertFixtureInFront(area: CaptureRegion) {
        ensureQaForeground()
        assertEquals("Only the synthetic fixture may be in front", fixture, ui.rootInActiveWindow?.packageName?.toString())
        val window = ui.windows.first { it.root?.packageName == fixture && it.isActive }
        assertNotNull("Expected the known green card", qaCardNode("Green door"))
        val roi = Rect(area.left, area.top, area.right, area.bottom)
        val bounds = Rect()
        window.getBoundsInScreen(bounds)
        assertTrue("The OCR crop must be inside the fixture", bounds.contains(roi))
        assertFalse("An unrelated window covers the OCR crop", ui.windows.any {
            it.layer > window.layer && it.root?.packageName != context.packageName &&
                Rect.intersects(roi, Rect().apply(it::getBoundsInScreen))
        })
    }

    private fun checkGreenAndStop(incoming: CountDownLatch, crop: CaptureRegion? = null): Long {
        val started = SystemClock.elapsedRealtime()
        trigger(crop)
        val deadline = SystemClock.elapsedRealtime() + 35_000
        while (!incoming.await(250, TimeUnit.MILLISECONDS) && SystemClock.elapsedRealtime() < deadline) {
            if (hasResult(context.getString(R.string.ocr_no_text_help))) metrics["feedback"] = "no-text"
            if (hasResult(context.getString(R.string.toast_capture_failed))) metrics["feedback"] = "capture-failed"
            if (hasResult("Зелёная дверь")) metrics["greenBeforeHttp"] = "true"
        }
        assertEquals("The synthetic green card did not reach the adapter", 0L, incoming.count)
        waitFor("the real floating window renders the known translation") { hasResult("Зелёная дверь") }
        val elapsed = SystemClock.elapsedRealtime() - started
        context.startService(CaptureService.stopIntent(context))
        waitFor("normal stop releases the capture") { released() && projectionOwner() == ProjectionOwner.NONE }
        return elapsed
    }

    private fun showPage(color: String) {
        ensureQaForeground()
        val text = if (color == "blue") "Blue door" else "Green door"
        shell("am start --user $user -W --activity-single-top -a android.intent.action.MAIN " +
            "-c android.intent.category.LAUNCHER -n $fixture/.PageActivity --es page $color")
        waitFor("visible owned $color card") { qaCardNode(text) != null }
    }

    private fun qaCardNode(text: String) = ui.windows.asSequence().mapNotNull { it.root }
        .filter { it.packageName == fixture }.flatMap { it.findAccessibilityNodeInfosByText(text).asSequence() }
        .firstOrNull { it.text?.toString() == text && it.isVisibleToUser }

    private fun openRequest() {
        ensureQaForeground()
        shell("am start --user $user -W --activity-reorder-to-front -a android.intent.action.MAIN " +
            "-c android.intent.category.LAUNCHER -n ${context.packageName}/${MainActivity::class.java.name}")
        waitFor("app activity resumed") {
            var started = false
            instrumentation.runOnMainSync {
                val home = ActivityLifecycleMonitorRegistry.getInstance().getActivitiesInStage(Stage.RESUMED)
                    .filterIsInstance<MainActivity>().firstOrNull { !it.isFinishing }
                if (home != null) {
                    home.startActivity(CaptureStartRequestActivity.newIntent(home))
                    started = true
                }
            }
            started
        }
    }

    // Never confirm a whole-display choice. Confirm the scope only when the system displays a
    // selected single-app option. Then choose the fixture's exact label in the system task picker.
    private fun chooseTaskConsent(grant: Boolean) {
        selectorStep = "waiting for permission dialog"
        var selectedScope = false
        var clickedTarget = false
        val packageOfPermissionUi = requireNotNull(context.getSystemService(android.media.projection.MediaProjectionManager::class.java))
            .createScreenCaptureIntent().component?.packageName
        val safePackages = setOfNotNull(packageOfPermissionUi, "com.android.systemui", "com.android.intentresolver",
            "com.android.permissioncontroller", "com.google.android.permissioncontroller")
        val singleLabels = localizedModeLabels(safePackages, "single_app") + setOf("a single app", "a specific app",
            "single app", "one app", "an app", "share one app", "share a single app", "record one app",
            "одно приложение", "только одно приложение", "отдельное приложение", "транслировать одно приложение")
        val entireLabels = localizedModeLabels(safePackages, "entire_screen") + setOf("the entire screen", "entire screen",
            "share entire screen", "whole screen", "full screen", "весь экран", "транслировать весь экран")
        waitFor("system single-app selection", 35_000) {
            if (clickedTarget && running()) return@waitFor true
            val root = ui.rootInActiveWindow ?: return@waitFor false
            if (root.packageName?.toString() !in safePackages) return@waitFor false
            ensureQaForeground()
            val nodes = nodesOf(root).filter { it.isVisibleToUser }.toList()
            val negative = nodes.firstOrNull { it.viewIdResourceName == "android:id/button2" ||
                label(it).lowercase() in setOf("cancel", "deny", "отмена", "отклонить") }
            if (!grant) return@waitFor negative != null && click(negative)
            val fixtureNode = nodes.firstOrNull { label(it) == fixtureLabel }
            val positive = nodes.firstOrNull { it.viewIdResourceName == "android:id/button1" } ?:
                nodes.firstOrNull { label(it).lowercase() in setOf("next", "continue", "start now", "share", "start",
                    "далее", "продолжить", "начать", "поделиться", "разрешить") }
            val single = nodes.firstOrNull { label(it).lowercase() in singleLabels }
            val full = nodes.firstOrNull { label(it).lowercase() in entireLabels }
            if (fixtureNode != null && !clickedTarget) {
                if (click(fixtureNode)) {
                    clickedTarget = true
                    selectorStep = "selected CT QA card"
                }
            } else if (!clickedTarget && single != null && !selectedScope) {
                val scopeAlreadySelected = full == null || isCheckedOption(single, entireLabels)
                if (scopeAlreadySelected && positive != null) {
                    selectedScope = click(positive)
                    selectorStep = "confirmed single-app scope"
                } else if (click(single)) {
                    selectorStep = "chose single-app option"
                }
            } else if (!clickedTarget && single == null && !selectedScope) {
                val spinner = nodes.firstOrNull { it.className?.toString()?.endsWith("Spinner") == true }
                if (spinner != null && click(spinner)) selectorStep = "opened system scope selector"
            } else if (clickedTarget && positive != null && click(positive)) {
                selectorStep = "confirmed selected CT QA card"
            }
            if (!clickedTarget && running()) error("A system projection started without selecting the synthetic task")
            clickedTarget && running()
        }
    }

    private fun confirmDefaultDisplay() {
        val manager = requireNotNull(context.getSystemService(android.media.projection.MediaProjectionManager::class.java))
        val systemPackage = manager.createScreenCaptureIntent().component?.packageName ?: "com.android.systemui"
        val trusted = setOf(systemPackage, "com.android.systemui")
        val fullLabels = localizedModeLabels(trusted, "entire_screen") + setOf("entire screen", "the entire screen",
            "share entire screen", "whole screen", "весь экран", "транслировать весь экран")
        selectorStep = "waiting for default-display permission"
        waitFor("system default-display consent") {
            val root = ui.rootInActiveWindow ?: return@waitFor false
            if (root.packageName?.toString() !in trusted) return@waitFor false
            ensureQaForeground()
            val nodes = nodesOf(root).filter { it.isVisibleToUser }.toList()
            val positive = nodes.firstOrNull { it.viewIdResourceName == "android:id/button1" } ?: return@waitFor false
            val negative = nodes.any { it.viewIdResourceName == "android:id/button2" }
            val projectionDialog = nodes.any {
                val id = it.viewIdResourceName?.substringAfterLast('/') ?: ""
                id.contains("media_projection") || id.contains("screen_share") || label(it).lowercase() in fullLabels
            }
            if (negative && projectionDialog && click(positive)) {
                selectorStep = "confirmed default-display system permission"
                true
            } else false
        }
    }

    private fun localizedModeLabels(packages: Set<String>, mode: String): Set<String> = buildSet {
        for (pkg in packages) {
            val resources = runCatching { context.packageManager.getResourcesForApplication(pkg) }.getOrNull() ?: continue
            for (name in listOf("screen_share_permission_dialog_option_$mode",
                "media_projection_entry_app_permission_dialog_option_text_$mode")) {
                val id = resources.getIdentifier(name, "string", pkg)
                if (id != 0) add(resources.getString(id).lowercase())
            }
        }
    }
    private fun isCheckedOption(single: AccessibilityNodeInfo, fullLabels: Set<String>): Boolean {
        var candidate: AccessibilityNodeInfo? = single
        repeat(4) {
            val row = candidate ?: return false
            val parts = nodesOf(row).toList()
            if (parts.any { label(it).lowercase() in fullLabels }) return false
            if (parts.any { it.isChecked || it.isSelected && it.isCheckable }) return true
            candidate = row.parent
        }
        return false
    }
    private fun label(node: AccessibilityNodeInfo) = (node.text ?: node.contentDescription ?: "").toString().trim()
    private fun nodesOf(root: AccessibilityNodeInfo): Sequence<AccessibilityNodeInfo> = sequence {
        yield(root)
        for (i in 0 until root.childCount) root.getChild(i)?.let { yieldAll(nodesOf(it)) }
    }
    private fun click(node: AccessibilityNodeInfo): Boolean {
        var current: AccessibilityNodeInfo? = node
        repeat(5) {
            val n = current ?: return false
            if (n.isEnabled && n.isClickable && n.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
            current = n.parent
        }
        return false
    }

    private fun trigger(crop: CaptureRegion? = null) {
        ensureQaForeground()
        waitFor("external synthetic task ready for capture") { !MainCaptureUiVisibility.snapshot().visible }
        if (crop != null) assertFixtureInFront(crop)
        context.startService(Intent(context, CaptureService::class.java).setAction(CaptureService.ACTION_TRIGGER_ONCE))
    }
    private fun hasResult(text: String): Boolean {
        fun visible(view: View): Boolean = view.isShown && ((view is TextView && view.text?.contains(text) == true) ||
            (view is ViewGroup && (0 until view.childCount).any { visible(view.getChildAt(it)) }))
        var result = false
        instrumentation.runOnMainSync { result = WindowInspector.getGlobalWindowViews().any(::visible) }
        return result
    }
    private fun displays() = requireNotNull(context.getSystemService(DisplayManager::class.java)).displays
        .filter { it.name == "Click'n'Translate截屏" }.map { it.displayId }
    private fun projectionOwner() = projectionOwner(shell("dumpsys media_projection"), context.packageName, context.applicationInfo.uid)
    private fun running() = CaptureServiceState.running.value && displays().size == 1 && projectionOwner() == ProjectionOwner.OURS
    private fun released() = !CaptureServiceState.running.value && displays().isEmpty() &&
        Thread.getAllStackTraces().keys.none { it.isAlive && it.name == "MediaProjection-Capture" }
    private fun ensureQaForeground() = check(shell("am get-current-user").trim() == user.toString()) { "QA user is no longer in foreground" }
    private fun waitFor(label: String, ms: Long = 25_000, condition: () -> Boolean) {
        val limit = SystemClock.elapsedRealtime() + ms
        do { if (condition()) return; SystemClock.sleep(140) } while (SystemClock.elapsedRealtime() < limit)
        val root = ui.rootInActiveWindow
        val ids = if (root?.packageName?.toString()?.contains("systemui") == true)
            nodesOf(root).mapNotNull { it.viewIdResourceName?.substringAfterLast('/') }.distinct().take(30).joinToString() else ""
        throw AssertionError("$label timed out; step=$selectorStep foreground=${root?.packageName} " +
            "systemIds=$ids running=${CaptureServiceState.running.value} displays=${displays()} owner=${projectionOwner()}")
    }
    private fun shell(command: String) =
        ParcelFileDescriptor.AutoCloseInputStream(ui.executeShellCommand(command)).bufferedReader().use { it.readText() }
}

private class CaptureMetrics : Timber.Tree() {
    private val latest = ConcurrentHashMap<String, String>()
    private val patterns = mapOf(
        "frame" to Regex("""mediaProjection frame image=(\d+x\d+)"""),
        "capture" to Regex("""screenshot completed type=(\w+) elapsedMs=(\d+) success=(true|false)"""),
        "screen" to Regex("""settings screen=(\d+x\d+) region=(full|\([-\d,]+\))"""),
        "work" to Regex("""workBitmap=(\d+x\d+) region=(full|\([-\d,]+\))"""),
        "fullStats" to Regex("""screenshot full=(\d+x\d+) stats=samples=(\d+) transparent=([\d.]+) dark=([\d.]+) luma=([\d.]+) range=(\d+\.\.\d+) blankLike=(true|false)"""),
        "cropStats" to Regex("""workBitmap stats=samples=(\d+) transparent=([\d.]+) dark=([\d.]+) luma=([\d.]+) range=(\d+\.\.\d+) blankLike=(true|false)"""),
        "firstOcr" to Regex("""firstBlocks engine=(\w+) count=(\d+)"""),
        "finalOcr" to Regex("""rawBlocks final count=(\d+)"""),
    )
    override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
        if (tag != "VerticalDiag") return
        for ((key, pattern) in patterns) {
            pattern.find(message)?.let { latest[key] = it.groupValues.drop(1).joinToString("/") }
        }
        if (message.contains("stop: no OCR blocks")) latest["emptyOcr"] = "true"
        if (message.contains("COORDINATE_SPACE_WARNING")) latest["geometryWarning"] = "true"
        if (message.contains("rawBlocks final #") && message.contains(" text=\"")) {
            latest["lastOcrKind"] = kind(message.substringAfter(" text=\"").substringBeforeLast('"'))
        }
    }
    fun kind(value: String): String = when (value.trim().lowercase()) {
        "green door" -> "known-green"
        "blue door" -> "known-blue"
        "green", "blue", "door" -> "known-fragment"
        "" -> "empty"
        else -> "other"
    }
    operator fun set(key: String, value: String) { latest[key] = value }
    fun summary(): String = latest.toSortedMap().entries.joinToString(" ") { "${it.key}=${it.value}" }
}

private enum class ProjectionOwner { NONE, OURS, OTHER, UNKNOWN }
private val tupleOwner = Regex("""(?m)^[ \t]*\(([^,\s()]+),[ \t]*uid[ \t]*=[ \t]*(\d+)\)[ \t]*:""")
private val fieldOwner = Regex("""(?m)^[ \t]*packageName:[ \t]*(\S+)[ \t]*\r?\n[ \t]*uid:[ \t]*(\d+)[ \t]*\r?$""")
private val noProjection = Regex("""(?im)^[ \t]*Media Projection:[ \t]*\r?\n[ \t]*null[ \t]*\r?$""")

private fun projectionOwner(dump: String, packageName: String, uid: Int): ProjectionOwner {
    val owners = (tupleOwner.findAll(dump) + fieldOwner.findAll(dump))
        .map { it.groupValues[1] to it.groupValues[2].toLongOrNull() }.toList()
    if (owners.any { it.first != packageName || it.second != uid.toLong() }) return ProjectionOwner.OTHER
    if (owners.isNotEmpty()) return ProjectionOwner.OURS
    return if (noProjection.containsMatchIn(dump)) ProjectionOwner.NONE else ProjectionOwner.UNKNOWN
}

class ProjectionOwnerFormatTest {
    @Test fun physicalAndEmulatorOwnersMustMatchBothPackageAndUserUid() {
        val pkg = "dev.clickn.translate.debug"
        val uid = 1010284
        val emulator = "Media Projection: \n($pkg, uid=$uid): TYPE_SCREEN_CAPTURE"
        val physical = "Projection:\n    packageName: $pkg\n    uid: $uid\n    userHandle: UserHandle{10}\n    type: TYPE_SCREEN_CAPTURE"
        for (dump in listOf(emulator, physical)) {
            assertEquals(ProjectionOwner.OURS, projectionOwner(dump, pkg, uid))
            assertEquals(ProjectionOwner.OTHER, projectionOwner(dump, pkg, uid + 1))
            assertEquals(ProjectionOwner.OTHER, projectionOwner(dump, "other.app", uid))
            assertEquals(ProjectionOwner.OTHER, projectionOwner(dump + "\n" + dump.replace(pkg, "other.app"), pkg, uid))
        }
        assertEquals(ProjectionOwner.NONE, projectionOwner("MEDIA PROJECTION MANAGER\nMedia Projection: \nnull\n", pkg, uid))
        assertEquals(ProjectionOwner.UNKNOWN, projectionOwner("dump unavailable", pkg, uid))
    }
}
