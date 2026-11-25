// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import dev.clickn.translate.data.Settings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectionScopePolicyTest {
    @Test fun normalModeDefaultsToFullDisplayAndAdvancedModeRetainsExplicitChoice() {
        // API 26/33 must never enter the API 34 config path, even for an explicit request.
        assertFalse(shouldRequestEntireScreen(26, true, true))
        assertFalse(shouldRequestEntireScreen(33, false, true))
        // Ordinary screen translation selects the whole display without another app-choice step.
        assertTrue(shouldRequestEntireScreen(34, false, false))
        assertTrue(shouldRequestEntireScreen(36, false, false))
        // Advanced users can still deliberately choose the system app-sharing dialog.
        assertFalse(shouldRequestEntireScreen(35, true, false))
        assertTrue(shouldRequestEntireScreen(35, true, true))
    }

    @Test fun normalDefaultDoesNotRewriteTheAdvancedPreferenceOrCallNewApisOnOlderAndroid() {
        assertFalse(Settings().shareEntireScreen)
        assertTrue(shouldRequestEntireScreen(34, false, Settings().shareEntireScreen))
        assertFalse(shouldRequestEntireScreen(34, true, false))
        assertTrue(shouldRequestEntireScreen(34, true, true))
        assertFalse(shouldRequestEntireScreen(26, false, true))
        assertFalse(shouldRequestEntireScreen(33, false, true))
    }
}
