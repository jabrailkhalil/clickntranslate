package dev.clickn.translate.ocr

import kotlinx.coroutines.CancellationException

/** Only stop() may cross threads. The native worker alone disposes its API after draining. */
internal class TesseractRecognitionOwner(private val stop: () -> Unit) {
    private val lock = Any()
    private var cancelled = false
    private var recognizing = false
    private var disposed = false
    private var sawNativeProgress = false
    val active: Boolean get() = synchronized(lock) { recognizing && !disposed }
    val progressSeen: Boolean get() = synchronized(lock) { sawNativeProgress && !disposed }

    fun begin() = synchronized(lock) {
        check(!disposed)
        ensureActiveLocked()
        recognizing = true
    }
    fun cancel() = synchronized(lock) {
        if (disposed) return@synchronized
        cancelled = true
        if (recognizing) stop()
    }
    fun progress() = synchronized(lock) {
        // Covers cancellation immediately before JNI starts/reset its hOCR monitor.
        if (!disposed && recognizing) {
            sawNativeProgress = true
            if (cancelled) stop()
        }
    }
    fun ensureActive() = synchronized(lock) { ensureActiveLocked() }
    private fun ensureActiveLocked() {
        if (cancelled) throw CancellationException("Arabic OCR cancelled")
    }
    fun dispose(release: () -> Unit) = synchronized(lock) {
        if (disposed) return@synchronized
        recognizing = false
        disposed = true
        release()
    }
}
