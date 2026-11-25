// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.capture

import android.content.Context
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import dev.clickn.translate.util.VerticalDiagnosticLog
import dev.clickn.translate.util.physicalDisplaySize
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.android.asCoroutineDispatcher
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.job
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.util.concurrent.atomic.AtomicBoolean
import timber.log.Timber

/** MediaProjection + VirtualDisplay + ImageReader screenshot implementation. */
class MediaProjectionScreenshotter(
    private val context: Context,
    private val projection: MediaProjection,
    private val onCaptureSizeChanged: (Int, Int) -> Unit = { _, _ -> },
    onProjectionStopped: () -> Unit = {},
) : Screenshotter {

    private val density = context.resources.configuration.densityDpi
    private val handlerThread = HandlerThread("MediaProjection-Capture").apply { start() }
    private val handler = Handler(handlerThread.looper)
    private val captureDispatcher = handler.asCoroutineDispatcher("MediaProjection-Capture")
    private val captureMutex = Mutex()
    private val startupLock = Any()
    // Accessed only on the capture handler; this is the withContext child, not its caller.
    private var activeCapture: Job? = null

    @Volatile private var width = 0
    @Volatile private var height = 0

    @Volatile private var imageReader: ImageReader? = null
    @Volatile private var virtualDisplay: VirtualDisplay? = null
    private val lifetime = MediaProjectionLifetime(::releaseResources, onProjectionStopped)

    private val projectionCallback = object : MediaProjection.Callback() {
        override fun onStop() {
            Timber.i("MediaProjection stopped by system / user")
            lifetime.systemStopped()
        }

        override fun onCapturedContentResize(width: Int, height: Int) {
            if (lifetime.isReleased) return
            // Report the source geometry even when the output surface already has this size.
            // The owner deduplicates the initial callback and repeated notifications.
            onCaptureSizeChanged(width, height)
            VerticalDiagnosticLog.i(
                "mediaProjection callback resize target=${width}x$height " +
                    "current=${this@MediaProjectionScreenshotter.width}x${this@MediaProjectionScreenshotter.height}"
            )
            resizeProjection(width, height, "capturedContentResize")
        }
    }

    /** The caller owns this instance before any platform setup can fail. */
    internal fun start() = synchronized(startupLock) {
        check(!lifetime.isReleased && imageReader == null) { "Projection cannot be started again" }
        // Keep MediaProjection and overlay windows in the same full-display coordinate space.
        val physicalSize = physicalDisplaySize(context)
        width = physicalSize.width
        height = physicalSize.height

        projection.registerCallback(projectionCallback, handler)

        val reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        imageReader = reader
        virtualDisplay = checkNotNull(projection.createVirtualDisplay(
            "Click'n'Translate截屏",
            width,
            height,
            density,
            MediaProjectionCaptureConfig.virtualDisplayFlags,
            reader.surface,
            null,
            handler,
        )) { "MediaProjection did not create a virtual display" }
        Timber.i(
            "MediaProjection ready: ${width}x$height @ $density dpi " +
                "flags=${MediaProjectionCaptureConfig.virtualDisplayFlags}"
        )
        VerticalDiagnosticLog.i(
            "mediaProjection ready configured=${width}x$height densityDpi=$density " +
                "flags=${MediaProjectionCaptureConfig.virtualDisplayFlags}"
        )
    }

    override val isReady: Boolean
        get() = !lifetime.isReleased && virtualDisplay != null

    internal fun diagnosticSummary(): String =
        "configured=${width}x$height densityDpi=$density ready=$isReady"

    internal fun resizeProjection(targetWidth: Int, targetHeight: Int, reason: String) {
        if (lifetime.isReleased) return
        VerticalDiagnosticLog.i(
            "mediaProjection resize requested reason=$reason current=${width}x$height " +
                "target=${targetWidth}x$targetHeight"
        )
        handler.post { resizeProjectionOnHandler(targetWidth, targetHeight, reason) }
    }

    private fun resizeProjectionOnHandler(targetWidth: Int, targetHeight: Int, reason: String) {
        if (lifetime.isReleased || !shouldResizeProjection(width, height, targetWidth, targetHeight)) return
        val display = virtualDisplay ?: return
        val oldReader = imageReader
        val newReader = runCatching {
            ImageReader.newInstance(targetWidth, targetHeight, PixelFormat.RGBA_8888, 2)
        }.onFailure {
            VerticalDiagnosticLog.w(it, "mediaProjection resize reader create failed reason=$reason")
        }.getOrNull() ?: return

        val resized = runCatching {
            display.setSurface(null)
            display.resize(targetWidth, targetHeight, density)
            display.setSurface(newReader.surface)
        }.onFailure {
            runCatching { display.setSurface(oldReader?.surface) }
            VerticalDiagnosticLog.w(
                it,
                "mediaProjection resize failed reason=$reason current=${width}x$height " +
                    "target=${targetWidth}x$targetHeight"
            )
        }.isSuccess
        if (!resized) {
            newReader.close()
            return
        }

        imageReader = newReader
        width = targetWidth
        height = targetHeight
        activeCapture?.cancel(CancellationException("MediaProjection reader resized"))
        runCatching { oldReader?.setOnImageAvailableListener(null, null) }
        runCatching { oldReader?.close() }
        VerticalDiagnosticLog.i(
            "mediaProjection resized reason=$reason configured=${width}x$height densityDpi=$density"
        )
    }

    override suspend fun capture(): Bitmap? = captureFrame(minTimestampNanos = null)

    /**
     * SurfaceFlinger's VirtualDisplay/Surface queues use CLOCK_MONOTONIC, as does
     * Android's System.nanoTime. ImageReader preserves that producer timestamp.
     * This comparison is specific to this producer, not to arbitrary Image sources.
     */
    override suspend fun captureAfter(minTimestampNanos: Long): Bitmap? =
        captureFrame(minTimestampNanos)

    private suspend fun captureFrame(minTimestampNanos: Long?): Bitmap? = captureMutex.withLock {
        var ownedBitmap: Bitmap? = null
        var capturedReader: ImageReader? = null
        try {
            val bitmap = withContext(captureDispatcher) {
                if (!isReady) return@withContext null
                val reader = imageReader ?: return@withContext null
                capturedReader = reader
                val captureJob = currentCoroutineContext().job
                activeCapture = captureJob
                try {
                    val image = awaitNextImage(reader, minTimestampNanos) ?: return@withContext null
                    try {
                        currentCoroutineContext().ensureActive()
                        if (!isReady || imageReader !== reader) return@withContext null
                        // Copy on the same HandlerThread that retires readers. A
                        // resize/release cannot invalidate the planes during copying.
                        imageToBitmap(image).also { ownedBitmap = it }
                    } finally {
                        image.close()
                    }
                } finally {
                    if (activeCapture === captureJob) activeCapture = null
                }
            }
            currentCoroutineContext().ensureActive()
            if (!isReady || imageReader !== capturedReader) return@withLock null
            ownedBitmap = null // Ownership passes to the caller only after dispatch.
            bitmap
        } catch (cancelled: CancellationException) {
            currentCoroutineContext().ensureActive() // Preserve caller cancellation.
            if (lifetime.isReleased || imageReader !== capturedReader) return@withLock null
            throw cancelled
        } finally {
            // withContext may cancel after creating the Bitmap, before returning it.
            ownedBitmap?.recycle()
        }
    }

    private suspend fun awaitNextImage(reader: ImageReader, minTimestampNanos: Long?): Image? {
        val image = awaitLatestFrame(
            source = object : LatestFrameSource<Image> {
                override fun acquireLatest(): Image? = acquireLatestImageOrNull(reader)

                override fun setOnFrameAvailableListener(listener: (() -> Unit)?) {
                    val callback = listener
                    val imageListener = callback?.let {
                        ImageReader.OnImageAvailableListener { callback() }
                    }
                    // Cancellation may detach from another thread after a resize
                    // has already closed this particular reader.
                    runCatching {
                        if (callback == null || (!lifetime.isReleased && imageReader === reader)) {
                            reader.setOnImageAvailableListener(imageListener, handler)
                        }
                    }.onFailure { Timber.d(it, "MediaProjection reader listener retired") }
                }
            },
            timeoutMs = NEXT_FRAME_TIMEOUT_MS,
            closeUndelivered = { it.close() },
            acceptFrame = {
                !lifetime.isReleased && imageReader === reader &&
                    (minTimestampNanos == null || it.timestamp > minTimestampNanos)
            },
            finalDrainOnTimeout = minTimestampNanos == null,
        )
        if (image == null) {
            Timber.w("Timed out waiting for next MediaProjection frame")
        }
        return image
    }

    private fun acquireLatestImageOrNull(reader: ImageReader): Image? =
        runCatching { reader.acquireLatestImage() }
            .onFailure { Timber.w(it, "Failed to acquire latest MediaProjection frame") }
            .getOrNull()

    private fun imageToBitmap(image: Image): Bitmap {
        val plane = image.planes[0]
        val buffer = plane.buffer
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val frameWidth = image.width
        val frameHeight = image.height
        val rowPadding = rowStride - pixelStride * frameWidth
        val bufferBytes = buffer.remaining()
        // Image.Plane only guarantees bytes through the final pixel, even with a padded stride.
        val shortLastRow = rowPadding > 0 && bufferBytes.toLong() < rowStride.toLong() * frameHeight
        val pixels = if (shortLastRow) {
            packImageRows(buffer, frameWidth * pixelStride, rowStride, frameHeight)
        } else buffer
        val bmpWidth = if (shortLastRow) frameWidth else frameWidth + rowPadding / pixelStride
        val raw = Bitmap.createBitmap(bmpWidth, frameHeight, Bitmap.Config.ARGB_8888)
        val output = try {
            raw.copyPixelsFromBuffer(pixels)
            if (bmpWidth == frameWidth) {
                raw
            } else {
                Bitmap.createBitmap(raw, 0, 0, frameWidth, frameHeight).also {
                    if (it !== raw) raw.recycle()
                }
            }
        } catch (failure: Throwable) {
            raw.recycle()
            throw failure
        }
        VerticalDiagnosticLog.i(
            "mediaProjection frame image=${image.width}x${image.height} configured=${width}x$height " +
                "pixelStride=$pixelStride rowStride=$rowStride rowPadding=$rowPadding " +
                "bufferBytes=$bufferBytes raw=${bmpWidth}x$frameHeight " +
                "output=${output.width}x${output.height}"
        )
        return output
    }

    override fun release() = lifetime.release()

    private fun releaseResources() {
        // Never close a reader while a capture on its worker is copying planes.
        if (Looper.myLooper() == handler.looper) {
            releaseResourcesOnHandler()
        } else if (!handler.post(::releaseResourcesOnHandler)) {
            // A stopped worker cannot still own an image copy.
            releaseResourcesOnHandler()
        }
    }

    private fun releaseResourcesOnHandler() = synchronized(startupLock) {
        // Cancel before quitting: Handler.quitSafely removes future timeout tasks.
        // Leaving a frame wait alive here could otherwise strand its continuation.
        activeCapture?.cancel(CancellationException("MediaProjection released"))
        try {
            virtualDisplay?.release()
        } catch (t: Throwable) {
            Timber.w(t, "VirtualDisplay release failed")
        }
        runCatching { imageReader?.setOnImageAvailableListener(null, null) }
        try {
            imageReader?.close()
        } catch (t: Throwable) {
            Timber.w(t, "ImageReader close failed")
        }
        runCatching { projection.unregisterCallback(projectionCallback) }
            .onFailure { Timber.w(it, "MediaProjection callback removal failed") }
        runCatching { projection.stop() }
            .onFailure { Timber.w(it, "MediaProjection stop failed") }
        handlerThread.quitSafely()
        virtualDisplay = null
        imageReader = null
        Timber.i("MediaProjectionScreenshotter released")
    }

    private companion object {
        const val NEXT_FRAME_TIMEOUT_MS = 2_000L
    }
}

/** Resource ownership only; the platform callback stays in the real screenshotter above. */
internal class MediaProjectionLifetime(
    private val releaseResources: () -> Unit,
    private val onProjectionStopped: () -> Unit,
) {
    private val released = AtomicBoolean(false)
    val isReleased: Boolean get() = released.get()

    fun release() {
        if (released.compareAndSet(false, true)) releaseResources()
    }

    fun systemStopped() {
        if (!released.compareAndSet(false, true)) return
        try { releaseResources() }
        finally { onProjectionStopped() }
    }
}
