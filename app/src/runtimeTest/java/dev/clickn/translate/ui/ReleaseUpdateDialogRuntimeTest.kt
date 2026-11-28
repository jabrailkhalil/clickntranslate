package dev.clickn.translate.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.core.app.ApplicationProvider
import android.content.Context
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.update.ReleaseApk
import dev.clickn.translate.update.UpdateInfo
import dev.clickn.translate.update.UpdateViewModel
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "ru-rRU-w840dp-h900dp")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class ReleaseUpdateDialogRuntimeTest {
    @get:Rule val compose = createComposeRule()

    private val apk = ReleaseApk("v1.8.3", "ClicknTranslate-1.8.3-arm64.apk", 60_000_000, "b".repeat(64))
    private val actions = mutableListOf<String>()

    private fun showUpdate(fontScale: Float = 1f, direction: LayoutDirection = LayoutDirection.Ltr) {
        compose.setContent {
            CompositionLocalProvider(
                LocalDensity provides Density(LocalDensity.current.density, fontScale),
                LocalLayoutDirection provides direction,
            ) {
                MaterialTheme {
                    UpdateResultDialog(
                        state = UpdateViewModel.State.Loaded(UpdateInfo("1.8.2", "1.8.3", apk, "Release notes. ".repeat(300))),
                        onDismiss = { actions += "later" },
                        onOpenRelease = { fail("unexpected external navigation") },
                        onSkipVersion = { actions += "skip:$it" },
                        onDownload = { assertEquals(apk, it); actions += "download" },
                        onInstall = { fail("unverified APK") },
                        onCancel = { fail("no transfer") },
                        onRetry = { fail("no failure") },
                    )
                }
            }
        }
    }

    @Test fun wideScreenKeepsTheUpdateDialogWithinItsReadingWidth() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        assertTrue("This scenario requires a tablet window", context.resources.configuration.screenWidthDp >= 800)
        showUpdate()
        compose.onNodeWithTag(UPDATE_DIALOG_TAG).assertWidthIsEqualTo(560.dp)
    }

    @Test
    @Config(qualifiers = "ru-rRU-w320dp-h800dp")
    fun narrowScreenWithLargeRtlTextCanReadAndActivateEveryUpdateAction() {
        showUpdate(fontScale = 1.7f, direction = LayoutDirection.Rtl)
        val context = ApplicationProvider.getApplicationContext<Context>()
        val buttons = listOf(R.string.update_dialog_btn_skip, R.string.update_dialog_btn_later, R.string.update_dialog_btn_download)
        val bounds = buttons.map { resource ->
            val label = context.getString(resource)
            val button = compose.onNodeWithText(label).assertIsDisplayed().assertHasClickAction()
            compose.onNodeWithText(label, useUnmergedTree = true)
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { read ->
                    val results = mutableListOf<TextLayoutResult>()
                    assertTrue(read(results))
                    val text = results.single()
                    assertFalse("$label overflows its bounds", text.hasVisualOverflow)
                    assertTrue("$label was compressed into a column of letters", text.lineCount <= 2)
                }
            button.performClick()
            button.fetchSemanticsNode().boundsInRoot
        }
        val dialog = compose.onNodeWithTag(UPDATE_DIALOG_TAG).fetchSemanticsNode().boundsInRoot
        bounds.forEach { box ->
            assertTrue("Action outside the dialog: $box", box.width > 0f && box.height > 0f &&
                box.left >= dialog.left - 1 && box.right <= dialog.right + 1 &&
                box.top >= dialog.top - 1 && box.bottom <= dialog.bottom + 1)
        }
        assertTrue("Expected actions to flow onto more than one row", bounds.map { it.top }.distinct().size > 1)
        assertEquals(listOf("skip:1.8.3", "later", "download"), actions)
    }
}
