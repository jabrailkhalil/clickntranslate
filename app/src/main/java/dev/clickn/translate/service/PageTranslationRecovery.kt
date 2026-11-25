package dev.clickn.translate.service

import java.util.concurrent.ConcurrentHashMap
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive

/**
 * Retries only unfinished units of the current screen, without repeating OCR or losing accepted
 * translations. The capture observer owns cancellation when the page/settings/session changes.
 * Provider/caller retries run inside an attempt; this delay prevents a failed page from becoming
 * a tight request loop after those attempts have been exhausted.
 */
internal suspend fun recoverPageTranslations(
    unitCount: Int,
    initialTranslations: Map<Int, String>,
    retryEnabled: Boolean,
    ensureCurrent: () -> Unit,
    onRetry: (pendingCount: Int, delayMs: Long) -> Unit = { _, _ -> },
    translatePending: suspend (indexes: List<Int>, accept: (Int, String) -> Unit) -> Unit,
): Map<Int, String> {
    require(unitCount >= 0)
    val accepted = ConcurrentHashMap<Int, String>()
    initialTranslations.forEach { (index, text) ->
        require(index in 0 until unitCount && text.isNotBlank())
        accepted[index] = text
    }
    var failures = 0
    while (true) {
        currentCoroutineContext().ensureActive()
        ensureCurrent()
        val pending = (0 until unitCount).filterNot(accepted::containsKey)
        if (pending.isEmpty()) return accepted.toMap()
        val pendingSet = pending.toSet()
        translatePending(pending) { index, text ->
            ensureCurrent()
            require(index in pendingSet) { "Translation does not belong to this attempt" }
            if (text.isNotBlank()) accepted[index] = text
        }
        currentCoroutineContext().ensureActive()
        ensureCurrent()
        val remaining = unitCount - accepted.size
        if (remaining == 0 || !retryEnabled) return accepted.toMap()
        failures = (failures + 1).coerceAtMost(5)
        val delayMs = pageRequestRetryDelayMs(failures)
        onRetry(remaining, delayMs)
        delay(delayMs)
    }
}

/** One indivisible current-page request, such as a provider that combines OCR and translation. */
internal suspend fun <T> retryCurrentPageRequest(
    retryEnabled: Boolean,
    ensureCurrent: () -> Unit,
    onRetry: (Throwable, Long) -> Unit = { _, _ -> },
    request: suspend () -> T,
): T {
    var failures = 0
    while (true) {
        currentCoroutineContext().ensureActive()
        ensureCurrent()
        val result = try {
            request()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            currentCoroutineContext().ensureActive()
            ensureCurrent()
            if (!retryEnabled) throw error
            failures = (failures + 1).coerceAtMost(5)
            val delayMs = pageRequestRetryDelayMs(failures)
            onRetry(error, delayMs)
            currentCoroutineContext().ensureActive()
            ensureCurrent()
            delay(delayMs)
            continue
        }
        // A response that completed after a page/settings/session change has no owner.
        currentCoroutineContext().ensureActive()
        ensureCurrent()
        return result
    }
}

private fun pageRequestRetryDelayMs(failures: Int): Long = when (failures) {
    1 -> 2_000L
    2 -> 4_000L
    3 -> 8_000L
    4 -> 16_000L
    else -> 30_000L
}
