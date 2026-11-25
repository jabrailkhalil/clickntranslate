package dev.clickn.translate.ui

import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Surface
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.android.resources.Density as ScreenDensity
import dev.clickn.translate.data.AppCompanion
import dev.clickn.translate.ui.theme.ClickTranslateTheme
import dev.clickn.translate.ui.theme.ThemeMode
import org.junit.Rule
import org.junit.Test

/** Explicit -PuiSnapshots only; production chooser, existing artwork, narrow screen and large type. */
class CompanionChoicesScreenshotTest {
    @get:Rule val paparazzi = Paparazzi(
        deviceConfig = DeviceConfig.PIXEL_5.copy(screenWidth = 320, screenHeight = 800,
            density = ScreenDensity.MEDIUM, locale = "ru"),
        theme = "android:Theme.Material.Light.NoActionBar",
    )

    @Test fun heroChoicesRussian320DpFont200() {
        paparazzi.snapshot {
            CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density, 2f)) {
                ClickTranslateTheme(ThemeMode.LIGHT) {
                    Surface(Modifier.fillMaxSize()) {
                        LazyColumn(contentPadding = PaddingValues(20.dp)) {
                            companionChoices(AppCompanion.CHESTER.id, null, {})
                        }
                    }
                }
            }
        }
    }
}
