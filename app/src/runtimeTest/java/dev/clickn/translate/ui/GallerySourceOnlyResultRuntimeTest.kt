package dev.clickn.translate.ui

import android.app.Application
import android.content.ClipboardManager
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.R
import dev.clickn.translate.gallery.GalleryItemStatus
import dev.clickn.translate.gallery.GalleryTranslationItemEntity
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = Application::class, qualifiers = "en-rUS-w400dp-h800dp")
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@LooperMode(LooperMode.Mode.PAUSED)
class GallerySourceOnlyResultRuntimeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun failedTranslationKeepsTheOcrTextAndOnlyOffersActionsForRealContent() {
        val app = ApplicationProvider.getApplicationContext<Application>()
        val clipboard = app.getSystemService(ClipboardManager::class.java)
        val placeholder = app.getString(R.string.gallery_item_no_translation)
        val source = "The photograph shows a lighthouse."
        val item = mutableStateOf(GalleryTranslationItemEntity(
            id = "item", taskId = "task", position = 0, sourceUri = "", displayName = "photo.png",
            status = GalleryItemStatus.FAILED, sourceText = source, errorMessage = "Service unavailable", updatedAtMs = 10,
        ))
        compose.setContent { MaterialTheme { GalleryResultItem(item.value, thumbnailLoader = { null }, onPreview = {}) } }
        val actions = compose.onAllNodesWithContentDescription(app.getString(R.string.gallery_text_actions))
        val copy = compose.onNodeWithText(app.getString(R.string.gallery_text_copy))
        compose.onNodeWithText(app.getString(R.string.gallery_status_failed)).assertIsDisplayed()
        compose.onNodeWithText(source).assertIsDisplayed()
        compose.onNodeWithText(placeholder).assertIsDisplayed()
        actions.assertCountEquals(2)
        actions[1].assertIsNotEnabled()
        actions[0].assertIsEnabled().performClick()
        copy.assertIsDisplayed().performClick()
        assertEquals(source, clipboard.primaryClip?.getItemAt(0)?.text?.toString())

        // A real translation can happen to match the localized placeholder exactly.
        compose.runOnIdle { item.value = item.value.copy(translatedText = placeholder) }
        compose.onNodeWithText(app.getString(R.string.gallery_status_partial)).assertIsDisplayed()
        actions[1].assertIsEnabled().performClick()
        copy.performClick()
        assertEquals(placeholder, clipboard.primaryClip?.getItemAt(0)?.text?.toString())

        compose.runOnIdle { item.value = item.value.copy(sourceText = "", translatedText = "") }
        actions.assertCountEquals(0)
        compose.onNodeWithText(app.getString(R.string.gallery_status_failed)).assertIsDisplayed()
    }
}
