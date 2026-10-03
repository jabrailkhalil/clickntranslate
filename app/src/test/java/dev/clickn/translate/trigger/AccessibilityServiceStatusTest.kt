// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.trigger

import org.junit.Assert.assertEquals
import org.junit.Test

class AccessibilityServiceStatusTest {
    @Test
    fun enabledServiceMatch_requiresExactPackageAndClass() {
        data class Case(
            val packageName: String?,
            val className: String?,
            val expected: Boolean,
        )

        listOf(
            Case("dev.clickn.translate.debug", "dev.clickn.translate.trigger.ClickTranslateAccessibilityService", true),
            Case("dev.clickn.translate", "dev.clickn.translate.trigger.ClickTranslateAccessibilityService", false),
            Case("dev.clickn.translate.debug", "com.example.OtherAccessibilityService", false),
            Case(null, "dev.clickn.translate.trigger.ClickTranslateAccessibilityService", false),
            Case("dev.clickn.translate.debug", null, false),
        ).forEach { case ->
            assertEquals(
                case.toString(),
                case.expected,
                matchesAccessibilityService(
                    packageName = case.packageName,
                    className = case.className,
                    expectedPackageName = "dev.clickn.translate.debug",
                    expectedClassName = "dev.clickn.translate.trigger.ClickTranslateAccessibilityService",
                ),
            )
        }
    }
}
