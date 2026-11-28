package dev.clickn.translate.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.ContextWrapper
import android.content.Intent
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.AppBrand
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.Settings
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode
import org.robolectric.shadows.ShadowToast

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "ru-rRU-w360dp-h800dp")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class SettingsHubLinksRuntimeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun websiteAndCommunityShowLocalizedFeedbackWhenNoBrowserCanOpenThem() {
        val base = ApplicationProvider.getApplicationContext<Context>()
        val requests = mutableListOf<String?>()
        val noBrowser = object : ContextWrapper(base) {
            override fun startActivity(intent: Intent) {
                assertEquals(Intent.ACTION_VIEW, intent.action)
                requests += intent.dataString
                throw ActivityNotFoundException()
            }
        }
        compose.setContent {
            CompositionLocalProvider(LocalContext provides noBrowser) {
                MaterialTheme {
                    SettingsHub(Settings(), onProvider = {}, onAppearance = {}, onLanguage = {},
                        onAdvanced = {}, onGlossary = {}, onDictionaries = {}, onLogs = {})
                }
            }
        }
        for (id in listOf(R.string.mobile_website, R.string.mobile_community)) {
            val title = base.getString(id)
            compose.onNodeWithTag("settings-hub").performScrollToNode(hasText(title))
            compose.onNodeWithText(title).performClick()
            assertEquals(base.getString(R.string.settings_external_browser_unavailable), ShadowToast.getTextOfLatestToast())
        }
        assertEquals(listOf(AppBrand.WEBSITE_URL, AppBrand.COMMUNITY_URL), requests)
    }
}
