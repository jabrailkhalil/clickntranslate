// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

internal interface LatestFrameSource<T> {
    fun acquireLatest(): T?
    fun setOnFrameAvailableListener(listener: (() -> Unit)?)
}

internal suspend fun <T> awaitLatestFrame(
    source: LatestFrameSource<T>,
    timeoutMs: Long,
    closeUndelivered: (T) -> Unit = {},
    acceptFrame: (T) -> Boolean = { true },
    finalDrainOnTimeout: Boolean = true,
): T? {
    fun acquireAccepted(): T? {
        val latest = source.acquireLatest() ?: return null
        val accepted = try {
            acceptFrame(latest)
        } catch (failure: Throwable) {
            closeUndelivered(latest)
            throw failure
        }
        if (accepted) return latest
        closeUndelivered(latest)
        return null
    }

    currentCoroutineContext().ensureActive()
    acquireAccepted()?.let { latest ->
        try {
            currentCoroutineContext().ensureActive()
            return latest
        } catch (failure: Throwable) {
            closeUndelivered(latest)
            throw failure
        }
    }

    // Keep ownership until withTimeoutOrNull has returned too: a timeout can win
    // after the listener resumed but before the caller receives that value.
    val ownedFrame = AtomicReference<T?>(null)
    fun closeOwned(frame: T) {
        if (ownedFrame.compareAndSet(frame, null)) closeUndelivered(frame)
    }
    try {
        val frame = withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine<T> { cont ->
                val finished = AtomicBoolean(false)

                fun tryResumeWithLatest() {
                    // A queued callback from a previous wait must not consume the
                    // next capture's frame after its listener has been detached.
                    if (finished.get() || !cont.isActive) return
                    val latest = acquireAccepted() ?: return
                    if (!finished.compareAndSet(false, true)) {
                        closeUndelivered(latest)
                        return
                    }
                    ownedFrame.set(latest)
                    source.setOnFrameAvailableListener(null)
                    cont.resume(latest) { _, undelivered, _ -> closeOwned(undelivered) }
                }

                cont.invokeOnCancellation {
                    if (finished.compareAndSet(false, true)) {
                        source.setOnFrameAvailableListener(null)
                    }
                }

                if (!cont.isActive) return@suspendCancellableCoroutine
                source.setOnFrameAvailableListener { tryResumeWithLatest() }
                // Cancellation can happen while the source installs its listener.
                if (finished.get() || !cont.isActive) {
                    source.setOnFrameAvailableListener(null)
                } else {
                    tryResumeWithLatest()
                }
            }
        }

        currentCoroutineContext().ensureActive()
        if (frame != null) {
            ownedFrame.compareAndSet(frame, null)
            return frame
        }
    } finally {
        ownedFrame.getAndSet(null)?.let(closeUndelivered)
    }

    if (!finalDrainOnTimeout) return null
    return acquireAccepted()?.let { latest ->
        try {
            currentCoroutineContext().ensureActive()
            latest
        } catch (failure: Throwable) {
            closeUndelivered(latest)
            throw failure
        }
    }
}
