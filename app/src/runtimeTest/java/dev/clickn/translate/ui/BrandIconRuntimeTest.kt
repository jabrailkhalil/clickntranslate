package dev.clickn.translate.ui

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.drawable.AdaptiveIconDrawable
import android.graphics.drawable.VectorDrawable
import android.net.Uri
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class BrandIconRuntimeTest {
    private val context get() = ApplicationProvider.getApplicationContext<Context>()
    @Test fun presetsLeaveExactlyOneLauncherEntry() {
        listOf(BrandIconPrefs.LOGO, BrandIconPrefs.MASCOT).forEach { choice ->
            BrandIconPrefs.write(context, choice)
            val active = if (choice == BrandIconPrefs.LOGO) "LauncherLogo" else "LauncherMascot"
            val inactive = if (choice == BrandIconPrefs.LOGO) "LauncherMascot" else "LauncherLogo"
            assertEquals(PackageManager.COMPONENT_ENABLED_STATE_ENABLED, context.packageManager.getComponentEnabledSetting(ComponentName(context.packageName, "dev.clickn.translate.$active")))
            assertEquals(PackageManager.COMPONENT_ENABLED_STATE_DISABLED, context.packageManager.getComponentEnabledSetting(ComponentName(context.packageName, "dev.clickn.translate.$inactive")))
        }
    }
    @Test fun customImagesAreBoundedAndFailedReplacementPreservesPicture() {
        val uri = Uri.parse("content://clickn.test/image")
        val bytes = ByteArrayOutputStream().also { Bitmap.createBitmap(2048, 1024, Bitmap.Config.ARGB_8888).compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
        shadowOf(context.contentResolver).registerInputStream(uri, ByteArrayInputStream(bytes))
        val image = BrandIconPrefs.importPicture(context, uri)
        assertEquals(512, image.width); assertEquals(256, image.height)
        shadowOf(context.contentResolver).registerInputStream(uri, ByteArrayInputStream(byteArrayOf(1, 2, 3)))
        assertThrows(IllegalArgumentException::class.java) { BrandIconPrefs.importPicture(context, uri) }
        assertEquals(512, BrandIconPrefs.bitmap(context)!!.width)
        assertThrows(IllegalArgumentException::class.java) { BrandIconPrefs.importPicture(context, Uri.parse("file:///etc/hosts")) }
    }
    @Test fun logoIsVectorAtEveryLauncherDensity() {
        listOf(160, 320, 640).forEach { dpi ->
            val localized = context.createConfigurationContext(Configuration(context.resources.configuration).apply { densityDpi = dpi })
            val icon = localized.getDrawable(R.mipmap.ic_launcher) as AdaptiveIconDrawable
            assertTrue(icon.foreground is VectorDrawable)
            assertTrue(localized.getDrawable(R.drawable.brand_logo) is VectorDrawable)
        }
    }
}
