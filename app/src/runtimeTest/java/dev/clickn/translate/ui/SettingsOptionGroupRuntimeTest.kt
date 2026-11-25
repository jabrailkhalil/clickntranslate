package dev.clickn.translate.ui

import android.content.Context
import android.content.res.Configuration
import android.os.LocaleList
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.OverlayTheme
import java.util.Locale
import kotlin.math.abs
import org.junit.Assert.*
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
class SettingsOptionGroupRuntimeTest {
    @get:Rule val compose = createComposeRule()

    private val themes = listOf(
        OverlayTheme.CLASSIC_DARK to R.string.settings_theme_classic_dark,
        OverlayTheme.AMBER_GOLD to R.string.settings_theme_amber_gold,
        OverlayTheme.PAPER_LIGHT to R.string.settings_theme_paper_light,
        OverlayTheme.FROST_GLASS to R.string.settings_theme_frost_glass,
        OverlayTheme.CUSTOM to R.string.settings_theme_custom,
    )

    @Test fun allRussianThemesFit280DpAt200PercentTextWithoutLetterColumnsOrOverlap() {
        val context = russianContext()
        showNarrowOptions(context) {
            OverlayThemeChoices(OverlayTheme.CLASSIC_DARK) {}
        }

        val labels = themes.map { context.getString(it.second) }
        assertEquals("This case must exercise the Russian resource", "Своя тема", labels.last())
        val bounds = labels.map { label ->
            compose.onNodeWithText(label).assertIsDisplayed().assertHasClickAction()
            assertLabelFits(label, maximumLines = 2)
            compose.onNodeWithText(label).fetchSemanticsNode().boundsInRoot
        }
        assertContainedAndSeparate(bounds)
        assertTrue("Five large labels must wrap as whole choices", bounds.map { it.top }.distinct().size > 1)
    }

    @Test fun everyThemeChoiceDispatchesOnceAndUpdatesTheActualSelectedSemantics() {
        val context = russianContext()
        val selected = mutableStateOf(OverlayTheme.CLASSIC_DARK)
        val selections = mutableListOf<OverlayTheme>()
        showNarrowOptions(context) {
            OverlayThemeChoices(selected.value) { theme ->
                selections += theme
                selected.value = theme
            }
        }

        val order = themes.drop(1) + themes.first()
        order.forEachIndexed { index, (theme, labelRes) ->
            compose.onNodeWithText(context.getString(labelRes)).performClick()
            themes.forEach { (candidate, candidateLabel) ->
                val node = compose.onNodeWithText(context.getString(candidateLabel))
                if (candidate == theme) node.assertIsSelected() else node.assertIsNotSelected()
            }
            compose.runOnIdle {
                assertEquals(order.take(index + 1).map { it.first }, selections)
                assertEquals(theme, selected.value)
            }
        }
    }

    @Test fun optionGroupPlacesRtlChoicesFromTheRightAndWrapsWithoutIntersections() {
        val context = russianContext()
        val labels = listOf("Раз", "Два", "Три", "Четыре")
        showNarrowOptions(context, LayoutDirection.Rtl) {
            SettingsOptionGroup {
                labels.forEach { label -> EngineChip("Раз", label, label) {} }
            }
        }

        val bounds = labels.map { label ->
            compose.onNodeWithText(label).assertIsDisplayed()
            compose.onNodeWithText(label).fetchSemanticsNode().boundsInRoot
        }
        assertContainedAndSeparate(bounds)
        val viewport = compose.onNodeWithTag(VIEWPORT).fetchSemanticsNode().boundsInRoot
        assertEquals("RTL starts at the right edge", viewport.right, bounds.first().right, 1f)
        assertTrue("The short labels must actually share a row to exercise RTL order", abs(bounds[0].top - bounds[1].top) < 1f)
        assertTrue("The second RTL choice must be left of the first", bounds[1].right <= bounds[0].left)
    }

    @Test fun fontChoiceGrowsForLargeTextAndExposesSelectionWithAnAccessibleTap() {
        val context = russianContext()
        val selected = mutableStateOf(false)
        var taps = 0
        val label = "Системный шрифт"
        showNarrowOptions(context) {
            OverlayFontChip(selected.value, label, onClick = {
                taps++
                selected.value = true
            })
        }

        val choice = compose.onNodeWithText(label)
        choice.assertIsDisplayed().assertIsNotSelected().assertHasClickAction()
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.Role, Role.RadioButton))
            .assert(SemanticsMatcher("Default font has no delete action") {
                SemanticsActions.OnLongClick !in it.config
            })
        val touchBounds = choice.getUnclippedBoundsInRoot()
        assertTrue("Font touch target must be at least48dp", touchBounds.bottom.value - touchBounds.top.value >= 48f)
        assertLabelFits(label, maximumLines = 2)
        choice.performTouchInput { click() }
        choice.assertIsSelected()
        compose.runOnIdle { assertEquals(1, taps) }
    }

    @Test fun importedFontLongPressDeletesWithoutAlsoSelectingAndTapDoesNotDelete() {
        val context = russianContext()
        var taps = 0
        var longPresses = 0
        val label = "Шрифт для комиксов"
        showNarrowOptions(context) {
            OverlayFontChip(
                selected = true,
                label = label,
                onClick = { taps++ },
                onLongClick = { longPresses++ },
            )
        }

        val choice = compose.onNodeWithText(label)
        choice.assertIsSelected()
        assertEquals(context.getString(R.string.settings_overlay_font_delete_action),
            choice.fetchSemanticsNode().config[SemanticsActions.OnLongClick].label)
        choice.performTouchInput { longClick() }
        compose.runOnIdle {
            assertEquals("Releasing a long press must not select the font", 0, taps)
            assertEquals(1, longPresses)
        }
        choice.performTouchInput { click() }
        compose.runOnIdle {
            assertEquals(1, taps)
            assertEquals("A short tap must not delete the font", 1, longPresses)
        }
    }

    private fun russianContext(): Context {
        val app = ApplicationProvider.getApplicationContext<ClickTranslateApp>()
        return app.createConfigurationContext(Configuration(app.resources.configuration).apply {
            setLocales(LocaleList(Locale.forLanguageTag("ru-RU")))
        })
    }

    private fun showNarrowOptions(
        context: Context,
        direction: LayoutDirection = LayoutDirection.Ltr,
        content: @Composable () -> Unit,
    ) {
        compose.setContent {
            CompositionLocalProvider(
                LocalContext provides context,
                LocalConfiguration provides context.resources.configuration,
                LocalDensity provides Density(LocalDensity.current.density, 2f),
                LocalLayoutDirection provides direction,
            ) {
                MaterialTheme {
                    Box(Modifier.width(280.dp).testTag(VIEWPORT)) { content() }
                }
            }
        }
    }

    private fun assertLabelFits(label: String, maximumLines: Int) {
        val textNode = compose.onNodeWithText(label, useUnmergedTree = true)
        val textBounds = textNode.fetchSemanticsNode().boundsInRoot
        val choiceBounds = compose.onNodeWithText(label).fetchSemanticsNode().boundsInRoot
        textNode.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { readLayout ->
                val results = mutableListOf<TextLayoutResult>()
                assertTrue(readLayout(results))
                val layout = results.single()
                val lineGeometry = (0 until layout.lineCount).map { line ->
                    "line$line(left=${layout.getLineLeft(line)},right=${layout.getLineRight(line)}," +
                        "start=${layout.getLineStart(line)},end=${layout.getLineEnd(line)})"
                }
                val lastGlyphOffset = layout.layoutInput.text.text.indexOfLast { !it.isWhitespace() }
                val lastGlyphBounds = if (lastGlyphOffset >= 0) layout.getBoundingBox(lastGlyphOffset) else null
                val diagnostic = "$label: ${layout.size}, lines=${layout.lineCount}, " +
                    "overflowWidth=${layout.didOverflowWidth}, overflowHeight=${layout.didOverflowHeight}, " +
                    "constraints=${layout.layoutInput.constraints}, " +
                    "paragraph=${layout.multiParagraph.width}x${layout.multiParagraph.height}, " +
                    "maxIntrinsicWidth=${layout.multiParagraph.intrinsics.maxIntrinsicWidth}, " +
                    "density=${layout.layoutInput.density}, fontSize=${layout.layoutInput.style.fontSize}, " +
                    "lineGeometry=$lineGeometry, lastGlyphOffset=$lastGlyphOffset, lastGlyph=$lastGlyphBounds, " +
                    "textBounds=$textBounds, choiceBounds=$choiceBounds"
                println("SETTINGS_OPTION_LAYOUT $diagnostic")
                // Compose1.7.6 reconstructs the String fast-path semantics paragraph with
                // its original maxWidth, even when the rendered Text is narrower. Check
                // every actual line/glyph against the rendered size instead of that allocation.
                assertFalse(diagnostic, layout.didOverflowHeight)
                for (line in 0 until layout.lineCount) {
                    assertFalse("Ellipsized label: $diagnostic", layout.isLineEllipsized(line))
                    assertTrue("Line starts outside Text: $diagnostic", layout.getLineLeft(line) >= 0f)
                    assertTrue("Line ends outside Text: $diagnostic", layout.getLineRight(line) <= layout.size.width)
                }
                layout.layoutInput.text.text.forEachIndexed { offset, char ->
                    if (!char.isWhitespace()) {
                        val glyph = layout.getBoundingBox(offset)
                        assertTrue("Glyph$offset clipped horizontally: $glyph / $diagnostic",
                            glyph.left >= 0f && glyph.right <= layout.size.width)
                        assertTrue("Glyph$offset clipped vertically: $glyph / $diagnostic",
                            glyph.top >= 0f && glyph.bottom <= layout.size.height)
                    }
                }
                assertTrue("Label must not form a column of letters: $diagnostic", layout.lineCount <= maximumLines)
            }
    }

    private fun assertContainedAndSeparate(bounds: List<Rect>) {
        val viewport = compose.onNodeWithTag(VIEWPORT).fetchSemanticsNode().boundsInRoot
        bounds.forEachIndexed { index, bound ->
            assertTrue("Choice$index starts outside viewport: $bound / $viewport", bound.left >= viewport.left - 1f)
            assertTrue("Choice$index ends outside viewport: $bound / $viewport", bound.right <= viewport.right + 1f)
            assertTrue("Choice$index is vertically clipped: $bound / $viewport",
                bound.top >= viewport.top - 1f && bound.bottom <= viewport.bottom + 1f)
            bounds.drop(index + 1).forEach { other ->
                val overlapWidth = minOf(bound.right, other.right) - maxOf(bound.left, other.left)
                val overlapHeight = minOf(bound.bottom, other.bottom) - maxOf(bound.top, other.top)
                assertFalse("Choices intersect: $bound / $other", overlapWidth > 1f && overlapHeight > 1f)
            }
        }
    }

    private companion object { const val VIEWPORT = "settings-options-viewport" }
}
