package dev.clickn.translate.ui

import android.content.res.Configuration
import android.graphics.Bitmap
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.unit.Density
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
import java.util.Locale
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
        val config = Configuration(app.resources.configuration).apply {
            setLocale(Locale.forLanguageTag("ru"))
            fontScale = 1.7f
        }
        assertTrue("This fixture needs a narrow handset, was ${config.screenWidthDp}dp", config.screenWidthDp in 300..340)
        val strings = app.createConfigurationContext(config)
        val apk = ReleaseApk("v1.8.3", "ClicknTranslate-1.8.3-arm64.apk", 60_000_000, "b".repeat(64))
        val offer = UpdateViewModel.State.Loaded(UpdateInfo("1.8.2", "1.8.3", apk, "Примечания к обновлению. ".repeat(30)))
        val taps = mutableListOf<String>()
        val previousLanguage = AppLocalePrefs.read(app)
        try {
            AppLocalePrefs.write(app, "ru")
            ActivityScenario.launch(MainActivity::class.java).use { scenario ->
                scenario.onActivity { activity ->
                    activity.setContent {
                        CompositionLocalProvider(
                            LocalConfiguration provides config,
                            LocalContext provides strings,
                            LocalDensity provides Density(LocalDensity.current.density, config.fontScale),
                            LocalLayoutDirection provides LayoutDirection.Rtl,
                        ) {
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
                for (button in listOf(R.string.update_dialog_btn_skip, R.string.update_dialog_btn_later, R.string.update_dialog_btn_download)) {
                    compose.onNodeWithText(strings.getString(button)).assertIsDisplayed().performTouchInput { click() }
                }
                compose.runOnIdle { assertEquals(listOf("skip", "later", "download"), taps) }
            }
        } finally {
            AppLocalePrefs.write(app, previousLanguage)
        }
    }
}
