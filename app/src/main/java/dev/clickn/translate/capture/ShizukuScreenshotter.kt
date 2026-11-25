package dev.clickn.translate.capture

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import java.io.IOException
import java.io.InputStream
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import rikka.shizuku.Shizuku
import timber.log.Timber

internal enum class ShizukuCaptureRoute { ACCESSIBILITY, SHELL, UNAVAILABLE }

internal fun resolveShizukuCaptureRoute(
    accessibilityReady: Boolean,
    shizukuReady: Boolean,
): ShizukuCaptureRoute = when {
    accessibilityReady -> ShizukuCaptureRoute.ACCESSIBILITY
    shizukuReady -> ShizukuCaptureRoute.SHELL
    else -> ShizukuCaptureRoute.UNAVAILABLE
}

/** Direct accessibility screenshots first; bounded raw shell capture then PNG for compatibility. */
class ShizukuScreenshotter internal constructor(
    private val accessibilityFastPath: Screenshotter,
    private val shellAvailable: () -> Boolean,
    private val createProcess: (Array<String>) -> Process?,
    private val processes: ShizukuCaptureProcessRunner = ShizukuCaptureProcessRunner(),
) : Screenshotter {
    constructor() : this(AccessibilityScreenshotter(), { Shizuku.pingBinder() }, Companion::newShizukuProcess)

    private val released = AtomicBoolean(false)
    private val request = Mutex()
    private val handoff = Any()

    private fun shizukuReady(): Boolean = runCatching(shellAvailable).getOrDefault(false)

    override val isReady: Boolean
        get() = !released.get() && resolveShizukuCaptureRoute(
            accessibilityFastPath.isReady, shizukuReady(),
        ) != ShizukuCaptureRoute.UNAVAILABLE

    override val minimumLoopObservationIntervalMs: Long
        get() = MIN_LOOP_OBSERVATION_INTERVAL_MS

    override suspend fun capture(): Bitmap? = request.withLock {
        val unconsumed = AtomicReference<Bitmap?>(null)
        try {
            val bitmap = withContext(Dispatchers.IO) {
                withTimeoutOrNull(5_000L) {
                    try {
                        captureFrame(unconsumed).also { currentCoroutineContext().ensureActive() }
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (error: Exception) {
                        Timber.w(error, "[shizuku-cap] capture failed")
                        null
                    }
                }
            }
            currentCoroutineContext().ensureActive()
            synchronized(handoff) {
                if (released.get() || bitmap == null) null else {
                    unconsumed.set(null)
                    bitmap
                }
            }
        } finally {
            // Includes cancellation during the IO-to-caller handoff and late accessibility frames.
            unconsumed.getAndSet(null)?.recycle()
        }
    }

    private suspend fun captureFrame(unconsumed: AtomicReference<Bitmap?>): Bitmap? {
        if (released.get()) return null
        val shellReady = shizukuReady()
        val route = resolveShizukuCaptureRoute(accessibilityFastPath.isReady, shellReady)
        if (route == ShizukuCaptureRoute.UNAVAILABLE) return null
        if (route == ShizukuCaptureRoute.ACCESSIBILITY) {
            accessibilityFastPath.capture()?.let { bitmap ->
                unconsumed.set(bitmap)
                return bitmap
            }
            if (!shellReady || released.get()) return null
        }
        val raw = executeScreencap(arrayOf("screencap"), "raw", ::readRawFrame)
        currentCoroutineContext().ensureActive()
        if (released.get()) return null
        raw?.let { ShizukuRawScreencapDecoder.decode(it) }?.let { bitmap ->
            unconsumed.set(bitmap)
            return bitmap
        }
        Timber.w("[shizuku-cap] raw capture/decode failed; retrying PNG")
        val png = executeScreencap(arrayOf("screencap", "-p"), "png") { it.readBytes() } ?: return null
        currentCoroutineContext().ensureActive()
        if (released.get()) return null
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(png, 0, png.size, bounds)
        if (bounds.outWidth !in 1..10_000 || bounds.outHeight !in 1..10_000 ||
            bounds.outWidth.toLong() * bounds.outHeight > 25_000_000) return null
        return BitmapFactory.decodeByteArray(png, 0, png.size)?.also(unconsumed::set)
    }

    private suspend fun executeScreencap(
        command: Array<String>,
        format: String,
        read: (InputStream) -> ByteArray,
    ): ByteArray? {
        if (released.get()) return null
        try {
            val result = processes.execute(createProcess = { createProcess(command) }, readOutput = read)
                ?: return null
            if (result.exitCode != 0) {
                Timber.w("[shizuku-cap] %s exit=%d stderr=%s", format, result.exitCode, result.error.take(300))
                return null
            }
            return result.output.takeIf { it.isNotEmpty() }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            Timber.w(error, "[shizuku-cap] %s capture failed", format)
            return null
        }
    }

    override fun release() {
        synchronized(handoff) { released.set(true) }
        processes.release()
        accessibilityFastPath.release()
    }

    private companion object {
        const val MIN_LOOP_OBSERVATION_INTERVAL_MS = 350L

        /** Allocate once from a validated header, accepting exactly the legacy or current frame. */
        fun readRawFrame(input: InputStream): ByteArray {
            val header = ByteArray(16)
            var total = readInto(input, header, 0)
            val probe = ShizukuRawScreencapDecoder.probeHeader(header.copyOf(total))
                ?: throw IOException("Invalid raw screenshot header")
            val currentFrameBytes = 16 + probe.pixelByteCount
            val frame = ByteArray(currentFrameBytes)
            header.copyInto(frame, endIndex = total)
            total += readInto(input, frame, total)
            if (input.read() >= 0) throw IOException("Raw screenshot has excess bytes")
            return when (total) {
                currentFrameBytes -> frame
                12 + probe.pixelByteCount -> frame.copyOf(total)
                else -> throw IOException("Raw screenshot size does not match header")
            }
        }

        fun readInto(input: InputStream, target: ByteArray, offset: Int): Int {
            var position = offset
            while (position < target.size) {
                val count = input.read(target, position, target.size - position)
                if (count < 0) break
                position += count
            }
            return position - offset
        }

        fun newShizukuProcess(command: Array<String>): Process? {
            val api = Shizuku::class.java
            val method = runCatching {
                api.getDeclaredMethod("newProcess", Array<String>::class.java, Array<String>::class.java, String::class.java)
            }.getOrNull() ?: api.declaredMethods.firstOrNull { it.name == "newProcess" } ?: return null
            method.isAccessible = true
            return method.invoke(null, command, null, null) as? Process
        }
    }
}
