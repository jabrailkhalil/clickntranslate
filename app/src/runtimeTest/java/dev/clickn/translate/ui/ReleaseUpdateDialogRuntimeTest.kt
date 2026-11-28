package dev.clickn.translate.ui

import android.content.Context
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.LayoutDirection
import androidx.test.core.app.ApplicationProvider
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

    private fun showUpdate(
        direction: LayoutDirection = LayoutDirection.Ltr,
        state: UpdateViewModel.State = UpdateViewModel.State.Loaded(UpdateInfo("1.8.2", "1.8.3", apk, "Release notes. ".repeat(300))),
    ) {
        compose.setContent {
            CompositionLocalProvider(
                LocalLayoutDirection provides direction,
            ) {
                MaterialTheme {
                    UpdateResultDialog(
                        state = state,
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

    @Test fun downloadedUpdateCanBeSkippedIndependentlyOfPostponingInstallation() {
        showUpdate(state = UpdateViewModel.State.Ready(apk))
        val context = ApplicationProvider.getApplicationContext<Context>()
        compose.onNodeWithText(context.getString(R.string.update_dialog_btn_later)).assertIsDisplayed().performClick()
        compose.onNodeWithText(context.getString(R.string.update_dialog_btn_skip)).assertIsDisplayed().performClick()
        assertEquals(listOf("later", "skip:1.8.3"), actions)
    }

    @Test
    @Config(qualifiers = "ru-rRU-w320dp-h800dp", fontScale = 1.7f)
    fun narrowScreenWithLargeRtlTextCanReadAndActivateEveryUpdateAction() {
        showUpdate(direction = LayoutDirection.Rtl)
        val dialogNode = compose.onNodeWithTag(UPDATE_DIALOG_TAG)
        val context = ApplicationProvider.getApplicationContext<Context>()
        val buttons = listOf(R.string.update_dialog_btn_skip, R.string.update_dialog_btn_later, R.string.update_dialog_btn_download)
        val minimumTouchSize = with(compose.density) { 48.dp.toPx() } - 1f
        val bounds = buttons.map { resource ->
            val label = context.getString(resource)
            val button = compose.onNodeWithText(label).assertIsDisplayed().assertHasClickAction()
            val touchBounds = button.fetchSemanticsNode().touchBoundsInRoot
            assertTrue("Small touch target for $label: $touchBounds",
                touchBounds.height >= minimumTouchSize && touchBounds.width >= minimumTouchSize)
            compose.onNodeWithText(label, useUnmergedTree = true)
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { read ->
                    val results = mutableListOf<TextLayoutResult>()
                    assertTrue(read(results))
                    val text = results.single()
                    assertEquals("Native dialog font scale", 1.7f, text.layoutInput.density.fontScale, 0.001f)
                    assertEquals(LayoutDirection.Rtl, text.layoutInput.layoutDirection)
                    val detail = "$label: size=${text.size}, paragraph=${text.multiParagraph.width}x${text.multiParagraph.height}, " +
                        "lines=${text.lineCount}, constraints=${text.layoutInput.constraints}"
                    assertFalse("Clipped vertically: $detail", text.didOverflowHeight)
                    assertTrue("Too many lines: $detail", text.lineCount <= 2)
                    for (line in 0 until text.lineCount) assertFalse("Ellipsis: $detail", text.isLineEllipsized(line))
                    // The String semantics path can remeasure its paragraph at the parent width.
                    // Inspect the ink positions against the actual measurement of this Text.
                    label.forEachIndexed { offset, char ->
                        if (!char.isWhitespace()) {
                            val glyph = text.getBoundingBox(offset)
                            assertTrue("Clipped glyph $offset at $glyph: $detail", glyph.left >= -0.5f &&
                                glyph.right <= text.size.width + 0.5f && glyph.top >= -0.5f &&
                                glyph.bottom <= text.size.height + 0.5f)
                        }
                    }
                }
            button.performTouchInput { click() }
            touchBounds
        }
        val dialog = dialogNode.fetchSemanticsNode().boundsInRoot
        bounds.forEachIndexed { index, box ->
            assertTrue("Action outside the dialog: $box", box.width > 0f && box.height > 0f &&
                box.left >= dialog.left - 1 && box.right <= dialog.right + 1 &&
                box.top >= dialog.top - 1 && box.bottom <= dialog.bottom + 1)
            bounds.take(index).forEach { other -> assertFalse("Overlapping actions: $box and $other", box.overlaps(other)) }
        }
        assertTrue("Expected actions to flow onto more than one row", bounds.map { it.top }.distinct().size > 1)
        assertEquals(listOf("skip:1.8.3", "later", "download"), actions)
    }
}
