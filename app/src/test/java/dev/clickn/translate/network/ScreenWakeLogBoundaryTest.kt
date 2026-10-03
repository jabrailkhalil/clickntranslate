// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.network

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class ScreenWakeLogBoundaryTest {
    @Test fun normalWakeRecoveryOnlyGoesToLogcat() {
        val source = File("src/main/java/dev/clickn/translate/network/ScreenWakeNetworkRecovery.kt").readText()
        assertFalse(source.contains("LogRepository"))
        listOf(
            "httpClient.connectionPool.evictAll()",
            "performanceDiagnostics.onScreenWake(",
            "Timber.tag(NETWORK_PERF_TAG).i(message)",
            "[network-wake] cleared idle cloud connections=",
        ).forEach { assertTrue(it, source.contains(it)) }
    }
}
