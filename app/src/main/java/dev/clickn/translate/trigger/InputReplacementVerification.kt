// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.trigger

import kotlinx.coroutines.delay

/** Read-only retries: never sends ACTION_SET_TEXT a second time. */
internal suspend fun awaitInputReplacement(
    pause: suspend (Long) -> Unit = { delay(it) },
    verify: suspend () -> Boolean,
): Boolean {
    for (attempt in 0..10) {
        if (verify()) return true
        if (attempt < 10) pause(120L)
    }
    return false
}
