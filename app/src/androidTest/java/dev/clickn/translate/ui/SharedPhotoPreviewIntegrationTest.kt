package dev.clickn.translate.ui

import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.net.Uri
import android.provider.DocumentsContract
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.clickn.translate.R
import dev.clickn.translate.data.AppLocalePrefs
import dev.clickn.translate.gallery.GalleryExportDocumentsFixture
import dev.clickn.translate.gallery.GalleryPrivateInputAccess
import dev.clickn.translate.gallery.GalleryTranslationWorkPolicy
import dev.clickn.translate.onboarding.OnboardingPrefs
import java.io.File
import java.util.Locale
import kotlin.math.abs
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SharedPhotoPreviewIntegrationTest {
    @get:Rule val compose = createEmptyComposeRule()

    @Test fun selectedPhotoCountUsesTheLocaleAndQuantity() {
        val app = InstrumentationRegistry.getInstrumentation().targetContext
        fun selected(language: String, count: Int): String {
            val config = Configuration(app.resources.configuration)
            config.setLocale(Locale.forLanguageTag(language))
            return app.createConfigurationContext(config).resources
                .getQuantityString(R.plurals.gallery_confirm_count, count, count)
        }

        assertEquals("1 image selected", selected("en", 1))
        assertEquals("2 images selected", selected("en", 2))
        assertEquals("Выбрано 2 изображения", selected("ru", 2))
        assertEquals("Выбрано 11 изображений", selected("ru", 11))
        assertEquals("Выбрано 21 изображение", selected("ru", 21))
        assertEquals("1 imagen seleccionada", selected("es", 1))
        assertEquals("1 image sélectionnée", selected("fr", 1))
        assertEquals("1 Bild ausgewählt", selected("de", 1))
        assertEquals("已选择 2 张图片", selected("zh-CN", 2))
    }

    private fun withSharedPhotos(count: Int, verify: (Context, ActivityScenario<MainActivity>) -> Unit) {
        assumeTrue(InstrumentationRegistry.getArguments().getString("sharedPreview") == "true")
        val app = InstrumentationRegistry.getInstrumentation().targetContext.applicationContext
        val parent = GalleryExportDocumentsFixture.parentUri()
        val photos = arrayListOf<Uri>()
        try {
            val bitmap = Bitmap.createBitmap(24, 24, Bitmap.Config.ARGB_8888)
            try {
                bitmap.eraseColor(Color.BLUE)
                repeat(count) { index ->
                    val uri = requireNotNull(DocumentsContract.createDocument(app.contentResolver, parent, "image/png", "rotate-$index.png"))
                    photos += uri
                    requireNotNull(app.contentResolver.openOutputStream(uri)).use {
                        assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it))
                    }
                }
            } finally { bitmap.recycle() }
            val intent = Intent(app, MainActivity::class.java).apply {
                action = Intent.ACTION_SEND_MULTIPLE
                type = "image/png"
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, photos)
                clipData = ClipData.newRawUri("images", photos.first()).apply {
                    photos.drop(1).forEach { addItem(ClipData.Item(it)) }
                }
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            ActivityScenario.launch<MainActivity>(intent).use { verify(AppLocalePrefs.wrap(app), it) }
        } finally {
            try { photos.forEach { DocumentsContract.deleteDocument(app.contentResolver, it) } }
            finally { GalleryExportDocumentsFixture.revoke(parent) }
        }
    }

    private fun display(matcher: SemanticsMatcher) {
        compose.waitUntil(10_000) { compose.onAllNodes(matcher).fetchSemanticsNodes().isNotEmpty() }
        compose.onNode(matcher).assertIsDisplayed()
    }

    private fun saveFrame(name: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        compose.waitForIdle()
        instrumentation.waitForIdleSync()
        val frame = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
        try {
            File(instrumentation.targetContext.filesDir, "qa-$name.png").outputStream().use {
                assertTrue(frame.compress(Bitmap.CompressFormat.PNG, 100, it))
            }
        } finally { frame.recycle() }
    }

    @Test fun largeBatchStillAsksForConfirmationAfterActivityRecreation() {
        val count = GalleryTranslationWorkPolicy.FOREGROUND_IMAGE_THRESHOLD
        withSharedPhotos(count) { strings, activity ->
            val create = hasText(strings.getString(R.string.gallery_confirm_create)) and hasClickAction() and isEnabled()
            display(create)
            compose.onNode(create).performClick()
            val summary = hasText(strings.resources.getQuantityString(R.plurals.gallery_confirm_create_dialog_message, count, count)) and hasAnyAncestor(isDialog())
            display(summary)
            activity.recreate()
            try { display(summary) } finally { saveFrame("gallery-review-recreated") }
            compose.onNode(hasText(strings.getString(android.R.string.cancel)) and hasAnyAncestor(isDialog())).performClick()
            display(create)
        }
    }

    @Test fun confirmedImportStaysInProgressAfterRecreationAndBackCanStillCancelIt() {
        withSharedPhotos(1) { strings, activity ->
            val create = hasText(strings.getString(R.string.gallery_confirm_create)) and hasClickAction() and isEnabled()
            val busy = hasText(strings.getString(R.string.gallery_confirm_creating))
            display(create)
            val holding = CompletableDeferred<Unit>()
            val release = CompletableDeferred<Unit>()
            val job = SupervisorJob()
            CoroutineScope(job + Dispatchers.IO).launch {
                GalleryPrivateInputAccess.rollback {
                    holding.complete(Unit)
                    release.await()
                }
            }
            try {
                runBlocking { withTimeout(10_000) { holding.await() } }
                compose.onNode(create).performClick()
                display(busy)
                activity.recreate()
                try { display(busy) } finally { saveFrame("gallery-preparing-recreated") }
                compose.onNode(create).assertDoesNotExist()
                activity.onActivity { it.onBackPressedDispatcher.onBackPressed() }
                display(hasText(strings.getString(R.string.mobile_nav_screen)) and hasClickAction())
                saveFrame("gallery-import-cancelled")
            } finally {
                release.complete(Unit)
                runBlocking { job.cancelAndJoin() }
            }
        }
    }

    @Test fun sharedPhotosKeepTheViewedPageOnRotationAndDiscardedSelectionStaysDiscarded() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("sharedPreview") == "true")
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val app = instrumentation.targetContext.applicationContext
        assertTrue(OnboardingPrefs.isCompleted(app))
        val strings = AppLocalePrefs.wrap(app)
        val first = strings.getString(R.string.gallery_preview_selected_name, 1)
        val second = strings.getString(R.string.gallery_preview_selected_name, 2)
        val secondColor = Color.rgb(177, 85, 55)
        val parent = GalleryExportDocumentsFixture.parentUri()
        val resolver = app.contentResolver
        val photos = arrayListOf<Uri>()

        fun makePhoto(name: String, color: Int) {
            val uri = requireNotNull(DocumentsContract.createDocument(resolver, parent, "image/png", "$name.png"))
            photos += uri
            val bitmap = Bitmap.createBitmap(180, 120, Bitmap.Config.ARGB_8888)
            try {
                bitmap.eraseColor(color)
                Canvas(bitmap).drawText(name, 8f, 26f, Paint(Paint.ANTI_ALIAS_FLAG).apply { this.color = Color.WHITE; textSize = 17f })
                requireNotNull(resolver.openOutputStream(uri)).use { assertTrue(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)) }
            } finally { bitmap.recycle() }
        }
        fun expectPhoto(label: String) {
            val title = hasText(label) and hasAnyAncestor(isDialog())
            val loaded = hasContentDescription(label) and hasAnyAncestor(isDialog())
            compose.waitUntil(15_000) { compose.onAllNodes(title).fetchSemanticsNodes().isNotEmpty() &&
                compose.onAllNodes(loaded).fetchSemanticsNodes().isNotEmpty() }
            compose.onNode(title).assertIsDisplayed()
            compose.onNode(loaded).assertIsDisplayed()
        }
        fun list() = compose.onNode(hasScrollToIndexAction())
        try {
            makePhoto("First", Color.rgb(36, 99, 143))
            makePhoto("Second", secondColor)
            val share = Intent(Intent.ACTION_SEND_MULTIPLE).setPackage(app.packageName).setType("image/png").apply {
                putParcelableArrayListExtra(Intent.EXTRA_STREAM, photos)
                clipData = ClipData.newRawUri("images", photos[0]).apply { addItem(ClipData.Item(photos[1])) }
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            val target = requireNotNull(share.resolveActivity(app.packageManager))
            assertEquals(MainActivity::class.java.name, target.className)
            share.component = target
            ActivityScenario.launch<MainActivity>(share).use { screen ->
                screen.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT }
                val thumbnail = hasContentDescription(first) and hasClickAction()
                compose.waitUntil(15_000) { compose.onAllNodes(hasScrollToIndexAction()).fetchSemanticsNodes().isNotEmpty() }
                list().performScrollToNode(thumbnail)
                compose.onNode(thumbnail).assertIsEnabled().performTouchInput { click() }
                expectPhoto(first)
                compose.onNode(isDialog()).performTouchInput { swipeLeft() }
                expectPhoto(second)
                screen.onActivity { it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE }
                compose.waitUntil(15_000) { app.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE }
                expectPhoto(second)
                instrumentation.waitForIdleSync()
                val frame = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
                val shot = try { requireNotNull(frame.copy(Bitmap.Config.ARGB_8888, false)) } finally { frame.recycle() }
                try {
                    File(app.filesDir, "qa-shared-preview-landscape.png").outputStream().use { assertTrue(shot.compress(Bitmap.CompressFormat.PNG, 100, it)) }
                    assertTrue("The frame must be landscape", shot.width > shot.height)
                    val pixel = shot.getPixel(shot.width / 2, shot.height / 2)
                    assertTrue("The decoded second photo must actually be visible at the center",
                        abs(Color.red(pixel) - Color.red(secondColor)) <= 3 &&
                        abs(Color.green(pixel) - Color.green(secondColor)) <= 3 &&
                        abs(Color.blue(pixel) - Color.blue(secondColor)) <= 3)
                } finally { shot.recycle() }
                compose.onNodeWithContentDescription(strings.getString(R.string.gallery_preview_close)).performClick()
                val remove = hasContentDescription(strings.getString(R.string.gallery_confirm_remove_photo, 1))
                list().performScrollToNode(remove)
                compose.onNode(remove).performClick()
                screen.recreate()
                val count = hasText(strings.resources.getQuantityString(R.plurals.gallery_confirm_count, 1, 1))
                compose.waitUntil(15_000) { compose.onAllNodes(hasScrollToIndexAction()).fetchSemanticsNodes().isNotEmpty() }
                list().performScrollToNode(count)
                compose.onNode(count).assertIsDisplayed()
                compose.onNodeWithContentDescription(strings.getString(R.string.common_back)).performClick()
                val home = hasText(strings.getString(R.string.mobile_nav_screen)) and hasClickAction()
                compose.waitUntil(15_000) { compose.onAllNodes(home).fetchSemanticsNodes().isNotEmpty() }
                screen.recreate()
                compose.waitUntil(15_000) { compose.onAllNodes(home).fetchSemanticsNodes().isNotEmpty() }
                compose.onNode(home).assertIsDisplayed()
                compose.onNodeWithText(strings.getString(R.string.gallery_confirm_title)).assertDoesNotExist()
            }
        } finally {
            try { photos.forEach { DocumentsContract.deleteDocument(resolver, it) } }
            finally { GalleryExportDocumentsFixture.revoke(parent) }
        }
    }
}
