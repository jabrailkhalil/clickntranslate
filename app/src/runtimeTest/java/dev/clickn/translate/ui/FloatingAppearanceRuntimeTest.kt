package dev.clickn.translate.ui

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import android.os.Looper
import android.widget.ImageView
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.data.*
import dev.clickn.translate.overlay.FloatingButtonManager
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class)
@LooperMode(LooperMode.Mode.PAUSED)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class FloatingAppearanceRuntimeTest {
    private val app get() = ApplicationProvider.getApplicationContext<ClickTranslateApp>()

    @Test fun changingCharacterRefreshesLiveButtonWithoutChangingAction() {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        val manager = FloatingButtonManager(app, {}, {}, {}, app.settingsRepository, scope)
        try {
            CompanionPrefs.write(app, AppCompanion.DOC.id)
            manager.skill = FloatingSkill.WORD_SELECT
            manager.show()
            val field = FloatingButtonManager::class.java.getDeclaredField("mainIcon").apply { isAccessible = true }
            val icon = field.get(manager) as ImageView
            assertEquals(0, icon.paddingLeft)
            val previous = icon.drawable
            CompanionPrefs.write(app, AppCompanion.CHESTER.id)
            shadowOf(Looper.getMainLooper()).idle()
            assertNotSame(previous, icon.drawable)
            assertEquals(FloatingSkill.WORD_SELECT, manager.skill)
            assertEquals(AppCompanion.CHESTER.id, CompanionPrefs.read(app))
            manager.hide()
            manager.show()
            assertEquals(0, (field.get(manager) as ImageView).paddingLeft)
            assertEquals(FloatingSkill.WORD_SELECT, manager.skill)
            CompanionPrefs.write(app, CompanionPrefs.ACTION)
            shadowOf(Looper.getMainLooper()).idle()
            assertTrue((field.get(manager) as ImageView).paddingLeft > 0)
        } finally { manager.hide(); scope.cancel() }
    }

    @Test fun customButtonPictureIsIndependentOfHeaderAndSurvivesBadImport() {
        val uri = Uri.parse("content://clickn.test/floating-image")
        val bytes = ByteArrayOutputStream().also {
            Bitmap.createBitmap(1200, 600, Bitmap.Config.ARGB_8888).compress(Bitmap.CompressFormat.PNG, 100, it)
        }.toByteArray()
        shadowOf(app.contentResolver).registerInputStream(uri, ByteArrayInputStream(bytes))
        val oldHeader = BrandIconPrefs.read(app)
        val imported = BrandIconPrefs.importPicture(app, uri, floating = true)
        CompanionPrefs.write(app, CompanionPrefs.CUSTOM)
        assertEquals(512, imported.width)
        assertEquals(oldHeader, BrandIconPrefs.read(app))
        shadowOf(app.contentResolver).registerInputStream(uri, ByteArrayInputStream(byteArrayOf(1, 2, 3)))
        assertThrows(IllegalArgumentException::class.java) { BrandIconPrefs.importPicture(app, uri, floating = true) }
        assertEquals(512, BrandIconPrefs.bitmap(app, floating = true)!!.width)
        assertEquals(CompanionPrefs.CUSTOM, CompanionPrefs.read(app))
    }
}
