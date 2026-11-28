package dev.clickn.translate.ui

import android.graphics.Bitmap
import android.os.Bundle
import android.os.ParcelFileDescriptor
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.R
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.update.ReleaseApk
import dev.clickn.translate.update.UpdateInfo
import dev.clickn.translate.update.UpdateViewModel
import java.io.File
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class UpdateDialogSurfaceIntegrationTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun largeRtlReleaseDialogRendersAndEveryVisibleActionCanBeTapped() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("updateSurface") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val app = instrumentation.targetContext.applicationContext
        val width = app.resources.configuration.screenWidthDp
        assertTrue("This fixture needs a narrow handset, was ${width}dp", width in 300..340)
        fun shell(command: String) = ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(command))
            .bufferedReader().use { it.readText().trim() }
        val previousScale = shell("settings get system font_scale")
        val apk = ReleaseApk("v1.8.3", "ClicknTranslate-1.8.3-arm64.apk", 60_000_000, "b".repeat(64))
        val offer = UpdateViewModel.State.Loaded(UpdateInfo("1.8.2", "1.8.3", apk, "Примечания к обновлению. ".repeat(30)))
        val taps = mutableListOf<String>()
        val previousLanguage = AppLocalePrefs.read(app)
        try {
            shell("settings put system font_scale 1.7")
            AppLocalePrefs.write(app, "ru")
            ActivityScenario.launch(MainActivity::class.java).use { scenario ->
                compose.waitUntil(15_000) { app.resources.configuration.fontScale == 1.7f }
                val strings = AppLocalePrefs.wrap(app)
                scenario.onActivity { activity ->
                    assertEquals(1.7f, activity.resources.configuration.fontScale, 0.001f)
                    activity.setContent {
                        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Rtl) {
                            MaterialTheme {
                                UpdateResultDialog(offer, onDismiss = { taps += "later" }, onOpenRelease = { fail() },
                                    onSkipVersion = { taps += "skip" }, onDownload = { taps += "download" },
                                    onInstall = { fail() }, onCancel = { fail() }, onRetry = { fail() })
                            }
                        }
                    }
                }
                compose.onNodeWithTag(UPDATE_DIALOG_TAG).assertIsDisplayed()
                instrumentation.waitForIdleSync()
                val systemBitmap = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
                val shot = try { requireNotNull(systemBitmap.copy(Bitmap.Config.ARGB_8888, false)) }
                finally { systemBitmap.recycle() }
                try {
                    val colors = mutableSetOf<Int>()
                    for (y in 0 until shot.height step 8) for (x in 0 until shot.width step 8) colors += shot.getPixel(x, y)
                    assertTrue("Expected a rendered app, screenshot has ${colors.size} colors", colors.size >= 16)
                    File(app.filesDir, "qa-update-320dp-large-rtl.png").outputStream().use {
                        assertTrue("Writing update dialog screenshot failed", shot.compress(Bitmap.CompressFormat.PNG, 100, it))
                    }
                } finally {
                    shot.recycle()
                }
                // Read the Text actually measured inside the separate native dialog window.
                compose.onNodeWithText(strings.getString(R.string.update_dialog_btn_skip), useUnmergedTree = true)
                    .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { read ->
                        val results = mutableListOf<TextLayoutResult>()
                        assertTrue(read(results))
                        val text = results.single()
                        val input = text.layoutInput
                        assertEquals("Dialog font scale", 1.7f, input.density.fontScale, 0.001f)
                        assertEquals("Dialog layout direction", LayoutDirection.Rtl, input.layoutDirection)
                        assertFalse("Action text height", text.didOverflowHeight)
                        instrumentation.addResults(Bundle().apply {
                            putString("updateDialogGeometry", "fontScale=${input.density.fontScale} density=${input.density.density} " +
                                "fontSize=${input.style.fontSize} lines=${text.lineCount} heightPx=${text.size.height}")
                        })
                    }
                for (button in listOf(R.string.update_dialog_btn_skip, R.string.update_dialog_btn_later, R.string.update_dialog_btn_download)) {
                    compose.onNodeWithText(strings.getString(button)).assertIsDisplayed().performTouchInput { click() }
                }
                compose.runOnIdle { assertEquals(listOf("skip", "later", "download"), taps) }
            }
        } finally {
            AppLocalePrefs.write(app, previousLanguage)
            if (previousScale == "null") shell("settings delete system font_scale") else shell("settings put system font_scale $previousScale")
        }
    }
}
