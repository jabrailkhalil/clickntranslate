// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.appcontext

import dev.clickn.translate.data.ForegroundAppDetectionMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ForegroundAppSelectionPolicyTest {
    @Test
    fun selection_cases() {
        val accessibility = ForegroundApp("game.a", "A", 100, ForegroundAppSource.ACCESSIBILITY)
        val usage = ForegroundApp("game.b", "B", 200, ForegroundAppSource.USAGE_ACCESS)
        data class Case(
            val mode: ForegroundAppDetectionMode,
            val accessibility: ForegroundApp?,
            val usage: ForegroundApp?,
            val expected: ForegroundApp?,
        )
        val cases = listOf(
            Case(ForegroundAppDetectionMode.AUTO, accessibility, usage, usage),
            Case(ForegroundAppDetectionMode.AUTO, accessibility, null, accessibility),
            Case(ForegroundAppDetectionMode.ACCESSIBILITY, accessibility, usage, accessibility),
            Case(ForegroundAppDetectionMode.USAGE_ACCESS, accessibility, usage, usage),
            Case(ForegroundAppDetectionMode.DISABLED, accessibility, usage, null),
        )
        cases.forEach { case ->
            assertEquals(
                case.toString(),
                case.expected,
                ForegroundAppSelectionPolicy.select(case.mode, case.accessibility, case.usage),
            )
        }
        assertNull(ForegroundAppSelectionPolicy.select(ForegroundAppDetectionMode.AUTO, null, null))
    }
}
