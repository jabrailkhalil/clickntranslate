package dev.clickn.translate.service

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Called on the service's main thread. Only the current start may retry a delayed Android grant. */
internal class CaptureForegroundStart(private val mainScope: CoroutineScope) {
    private var pendingRetry: Job? = null

    fun start(promote: () -> Unit, onReady: () -> Unit, onRetryFailed: (Exception) -> Unit) {
        cancel()
        try {
            promote()
        } catch (_: SecurityException) {
            // Some Android versions deliver consent before the project_media app-op becomes visible.
            pendingRetry = mainScope.launch {
                delay(200L)
                pendingRetry = null
                try {
                    promote()
                    onReady()
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    onRetryFailed(error)
                }
            }
            return
        }
        onReady()
    }

    fun cancel() {
        pendingRetry?.cancel()
        pendingRetry = null
    }
}
