package dev.clickn.translate.ui

import android.content.Context
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "ru-rRU-w360dp-h800dp")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class MobileLanguageSheetRuntimeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun localizedAutoSearchSurvivesRecreationAndCanBeSelected() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val query = "  ${context.getString(R.string.mobile_auto)}  "
        val restored = StateRestorationTester(compose)
        val selections = mutableListOf<String>()
        restored.setContent {
            MaterialTheme { LanguageSheet(isSource = true, selected = "auto") { selections += it } }
        }
        compose.onNode(hasSetTextAction()).performTextReplacement(query)
        compose.onNode(hasText("auto") and isSelectable()).assertIsDisplayed().assertIsSelected()

        restored.emulateSavedInstanceStateRestore()

        compose.onNode(hasSetTextAction()).assertTextContains(query)
        compose.onNode(hasText("auto") and isSelectable()).performClick()
        assertEquals(listOf("auto"), selections)
        compose.onNode(hasSetTextAction()).performTextReplacement("qx-invalid")
        compose.onNodeWithText(context.getString(R.string.lang_picker_no_match)).assertIsDisplayed()
    }

    @Test fun offlinePickerShowsSupportedCodesAliasesAndNoUnsupportedEntries() {
        val selected = mutableListOf<String>()
        compose.setContent {
            MaterialTheme { LanguageSheet(isSource = false, selected = "no", mlKitOnly = true) { selected += it } }
        }
        for (code in listOf("nb", "th", "vi", "kn")) {
            compose.onNode(hasSetTextAction()).performTextReplacement(code)
            val option = compose.onNode(hasText(code) and isSelectable()).assertIsDisplayed()
            if (code == "nb") option.assertIsSelected()
            option.performClick()
        }
        assertEquals(listOf("nb", "th", "vi", "kn"), selected)
        for (excluded in listOf("auto", "yue")) {
            compose.onNode(hasSetTextAction()).performTextReplacement(excluded)
            compose.onNode(hasText(excluded) and isSelectable()).assertDoesNotExist()
        }
    }
}
