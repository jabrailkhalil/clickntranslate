package dev.clickn.translate.service

import android.graphics.Bitmap
import android.os.Handler
import android.os.Looper
import android.view.Choreographer
import dev.clickn.translate.overlay.SourceObservationLease
import kotlin.coroutines.resume
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext

/** The caller holds its screenshot mutex throughout this operation. */
internal class SourceObservationCapture(
    private val mainDispatcher: CoroutineDispatcher = Dispatchers.Main.immediate,
    private val settle: suspend () -> Unit = ::settleSourceObservation,
    private val nanoTime: () -> Long = System::nanoTime,
) {
    /** Register each lease immediately, including when a subsequent manager can throw. */
    class LeaseCollector internal constructor(private val leases: MutableList<SourceObservationLease>) {
        fun add(lease: SourceObservationLease) {
            leases += lease
        }
    }

    suspend fun capture(
        isValid: () -> Boolean,
        acquire: LeaseCollector.() -> Unit,
        capture: suspend (freshAfterNanos: Long?) -> Bitmap?,
    ): Bitmap? {
        val leases = ArrayList<SourceObservationLease>()
        var ownedBitmap: Bitmap? = null
        var result: Bitmap? = null
        var failure: Throwable? = null
        try {
            try {
                val preparation = withContext(mainDispatcher) {
                    if (!isValid()) return@withContext null
                    val fence = nanoTime()
                    LeaseCollector(leases).acquire()
                    val changedVisibility = leases.any { it.changedVisibility }
                    if (changedVisibility) settle()
                    currentCoroutineContext().ensureActive()
                    if (isValid()) Preparation(fence.takeIf { changedVisibility }) else null
                }
                if (preparation != null) {
                    // Own the returned bitmap before the next cancellation/dispatcher boundary.
                    ownedBitmap = capture(preparation.freshAfterNanos)
                    currentCoroutineContext().ensureActive()
                    if (withContext(mainDispatcher) { isValid() }) result = ownedBitmap
                }
            } catch (error: Throwable) {
                failure = error
                throw error
            } finally {
                withContext(NonCancellable + mainDispatcher) {
                    var restorationFailure: Throwable? = null
                    for (index in leases.lastIndex downTo 0) {
                        try {
                            leases[index].close()
                        } catch (error: Throwable) {
                            val previous = restorationFailure
                            if (previous == null) restorationFailure = error
                            else if (previous !== error) previous.addSuppressed(error)
                        }
                    }
                    restorationFailure?.let { error ->
                        val previous = failure
                        if (previous == null) throw error
                        if (previous !== error) previous.addSuppressed(error)
                    }
                }
            }
            currentCoroutineContext().ensureActive()
            // Restoration must succeed before bitmap ownership can move to the caller.
            if (result != null) ownedBitmap = null
            return result
        } finally {
            ownedBitmap?.takeUnless { it.isRecycled }?.recycle()
        }
    }

    private data class Preparation(val freshAfterNanos: Long?)
}

private suspend fun settleSourceObservation() {
    awaitSourceObservationFrame()
    delay(80L)
}

private suspend fun awaitSourceObservationFrame() = suspendCancellableCoroutine<Unit> { continuation ->
    val choreographer = Choreographer.getInstance()
    val mainLooper = Looper.getMainLooper()
    val handler = Handler(mainLooper)
    val callback = Choreographer.FrameCallback {
        if (continuation.isActive) continuation.resume(Unit)
    }
    choreographer.postFrameCallback(callback)
    continuation.invokeOnCancellation {
        if (Looper.myLooper() == mainLooper) choreographer.removeFrameCallback(callback)
        else handler.post { choreographer.removeFrameCallback(callback) }
    }
}
