// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.shizuku

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class AccessibilityGrantPolicyTest {
    private val pkg = "dev.clickn.translate.debug"
    private val cls = "dev.clickn.translate.trigger.ClickTranslateAccessibilityService"
    private val own = "$pkg/$cls"

    @Test fun mergingKeepsOtherServicesAndNeverDuplicatesOwnComponent() {
        listOf(null to own, "" to own, "null" to own,
            "other/.Service" to "other/.Service:$own",
            "other/.Service:$own" to "other/.Service:$own",
            "$own:other/.Service" to "$own:other/.Service",
            "one/.A:two/.B" to "one/.A:two/.B:$own"
        ).forEach { (input, expected) ->
            assertEquals(expected, withAccessibilityService(input, pkg, cls))
        }
        assertEquals("dev.clickn.translate/.trigger.ClickTranslateAccessibilityService",
            withAccessibilityService("dev.clickn.translate/.trigger.ClickTranslateAccessibilityService",
                "dev.clickn.translate", cls))
        assertEquals("dev.clickn.translate/$cls:$own",
            withAccessibilityService("dev.clickn.translate/$cls", pkg, cls))
    }

    @Test fun commandsAreUserScopedAndPassTheListAsOneArgument() {
        for (user in listOf(0, 10, 999)) {
            assertArrayEquals(arrayOf("settings", "--user", "$user", "get", "secure", "enabled_accessibility_services"),
                accessibilitySettingsCommand(user))
            val value = "other/.Service:$own"
            assertArrayEquals(arrayOf("settings", "--user", "$user", "put", "secure", "enabled_accessibility_services", value),
                accessibilitySettingsCommand(user, value))
            assertEquals(user.toString(), overlayPermissionAppOpsCommand(pkg, user.toString())[3])
        }
    }

    @Test fun onlyTwoPermissionsAndNoBackgroundReenable() {
        val text = File("src/main/java/dev/clickn/translate/shizuku/AppPermissionCoordinator.kt").readText()
        assertTrue(text.contains("AccessibilityServiceStatus.isEnabled(context)"))
        assertTrue(text.contains("ClickTranslateAccessibilityService.isConnected()"))
        assertTrue(text.contains("withAccessibilityService(previous, context.packageName"))
        for (forbidden in listOf("pm grant", "WRITE_SECURE_SETTINGS", "ACCESSIBILITY_ENABLED",
            "BATTERY", "PACKAGE_USAGE_STATS", "addBinderReceivedListener", "createScreenCaptureIntent")) {
            assertFalse(forbidden, text.contains(forbidden))
        }
    }

    @Test fun rejectsInvalidUserOrComponent() {
        for (call in listOf<() -> Unit>(
            { accessibilitySettingsCommand(-1) },
            { withAccessibilityService(null, "bad;package", cls) },
            { withAccessibilityService(null, pkg, "bad/class") },
        )) {
            try { call(); fail("expected validation failure") } catch (_: IllegalArgumentException) { }
        }
    }
}
