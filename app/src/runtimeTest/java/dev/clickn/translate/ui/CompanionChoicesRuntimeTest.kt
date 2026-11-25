package dev.clickn.translate.ui

import android.content.Context
import android.content.ContextWrapper
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.data.AppCompanion
import dev.clickn.translate.data.CompanionPrefs
import java.util.UUID
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "en-rUS")
@LooperMode(LooperMode.Mode.PAUSED)
class CompanionChoicesRuntimeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun confirmingSetupWritesOnlyAMissingChoiceAndPreservesCustomLegacyAndVisibility() {
        val app = ApplicationProvider.getApplicationContext<ClickTranslateApp>()
        val name = "companion-owned-${UUID.randomUUID()}"
        val owned = object : ContextWrapper(app) {
            override fun getSharedPreferences(requested: String, mode: Int) = app.getSharedPreferences(name, mode)
        }
        val preferences = app.getSharedPreferences(name, Context.MODE_PRIVATE)
        try {
            CompanionPrefs.setKeepVisible(owned, true)
            assertFalse(CompanionPrefs.hasSelection(owned))
            assertEquals(AppCompanion.CHESTER.id, CompanionPrefs.read(owned))
            assertFalse("Displaying the default is not an explicit choice", CompanionPrefs.hasSelection(owned))
            assertEquals(AppCompanion.CHESTER.id, CompanionPrefs.confirmSelection(owned))
            assertTrue(CompanionPrefs.hasSelection(owned))
            val revision = preferences.getLong("revision", 0)
            CompanionPrefs.confirmSelection(owned)
            assertEquals(revision, preferences.getLong("revision", 0))

            for (id in listOf(CompanionPrefs.CUSTOM, CompanionPrefs.ACTION, CompanionPrefs.LOGO, "doc")) {
                CompanionPrefs.write(owned, id)
                val chosenRevision = preferences.getLong("revision", 0)
                assertEquals(id, CompanionPrefs.confirmSelection(owned))
                assertEquals(chosenRevision, preferences.getLong("revision", 0))
                assertTrue(CompanionPrefs.keepVisible(owned))
            }
            preferences.edit().putString("choice", "mochi").commit()
            assertTrue(CompanionPrefs.hasSelection(owned))
            assertEquals(AppCompanion.CHESTER.id, CompanionPrefs.confirmSelection(owned))
            assertEquals("mochi", preferences.getString("choice", null))
        } finally { app.deleteSharedPreferences(name) }
    }

    @Test fun everyNameFitsA320DpChooserAt200PercentTextAndTheLastChoiceIsReachable() {
        val selected = mutableStateOf(CompanionPrefs.CUSTOM)
        compose.setContent {
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                MaterialTheme {
                    LazyColumn(Modifier.width(320.dp).height(480.dp).testTag("companion-options")) {
                        companionChoices(selected.value, null) { selected.value = it }
                    }
                }
            }
        }
        for ((id, _) in companionChoiceOptions(CompanionPrefs.CUSTOM, false)) {
            compose.onNodeWithTag("companion-options").performScrollToNode(hasTestTag("companion-$id"))
            compose.onNodeWithTag("companion-$id").performScrollTo().assertIsDisplayed().assertHasClickAction()
            compose.onNodeWithTag("companion-name-$id", useUnmergedTree = true)
                .performSemanticsAction(SemanticsActions.GetTextLayoutResult) { readLayout ->
                    val layouts = mutableListOf<TextLayoutResult>()
                    assertTrue(readLayout(layouts))
                    assertEquals(1, layouts.size)
                    val layout = layouts.single()
                    val diagnostic = "id=$id size=${layout.size.width}x${layout.size.height} " +
                        "paragraph=${layout.multiParagraph.width}x${layout.multiParagraph.height} " +
                        "max=${layout.layoutInput.constraints.maxWidth}x${layout.layoutInput.constraints.maxHeight} " +
                        "lines=${layout.lineCount} overflowWidth=${layout.didOverflowWidth} overflowHeight=${layout.didOverflowHeight}"
                    println("COMPANION_LAYOUT $diagnostic")
                    assertFalse("$id clipped at 320dp/font200% ($diagnostic)", layout.hasVisualOverflow)
                }
        }
        compose.onNodeWithTag("companion-custom").assertIsSelected()
        compose.onNodeWithTag("companion-options").performScrollToNode(hasTestTag("companion-doc"))
        compose.onNodeWithTag("companion-doc").performScrollTo().performClick()
        assertEquals(AppCompanion.DOC.id, selected.value)
        compose.onNodeWithTag("companion-doc").assertIsSelected()
    }
}
