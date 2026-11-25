package dev.clickn.translate.capture

import dev.clickn.translate.shizuku.waitForPermissionProcess
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

internal data class ShizukuCaptureProcessResult<T>(val exitCode: Int, val output: T, val error: String)

/** Binary counterpart to the permission runner: owns one bounded, cancellable remote command. */
internal class ShizukuCaptureProcessRunner(
    private val waitForProcess: (Process, Long) -> Boolean = ::waitForPermissionProcess,
) {
    private val execution = Mutex()
    private val ownership = Any()
    private var released = false
    private var active: OwnedProcess? = null

    suspend fun <T> execute(
        createProcess: () -> Process?,
        timeoutMillis: Long = 5_000,
        maxOutputBytes: Int = MAX_FRAME_BYTES,
        readOutput: (InputStream) -> T,
    ): ShizukuCaptureProcessResult<T>? = execution.withLock {
        require(timeoutMillis > 0 && maxOutputBytes in 1..MAX_FRAME_BYTES)
        if (isReleased()) return@withLock null
        var owned: OwnedProcess? = null
        try {
            val result = withContext(Dispatchers.IO) {
                withTimeoutOrNull(timeoutMillis) {
                    currentCoroutineContext().ensureActive()
                    val process = createProcess() ?: return@withTimeoutOrNull null
                    val current = OwnedProcess(process).also { owned = it }
                    val accepted = synchronized(ownership) {
                        if (released) false else { active = current; true }
                    }
                    if (!accepted) return@withTimeoutOrNull null
                    coroutineScope {
                        try {
                            val output = async(Dispatchers.IO) {
                                val context = currentCoroutineContext()
                                readOutput(LimitedCaptureInput(current.stdout, maxOutputBytes) { context.ensureActive() })
                            }
                            val errors = async(Dispatchers.IO) {
                                val context = currentCoroutineContext()
                                LimitedCaptureInput(current.stderr, MAX_ERROR_BYTES) { context.ensureActive() }
                                    .readBytes().toString(Charsets.UTF_8)
                            }
                            // Reuse the dedicated Shizuku timed wait; inherited Process.waitFor(timeout)
                            // polls exitValue and is unsafe for a still-running Binder process.
                            while (true) {
                                currentCoroutineContext().ensureActive()
                                if (isReleased()) return@coroutineScope null
                                if (waitForProcess(process, minOf(100L, timeoutMillis))) break
                            }
                            currentCoroutineContext().ensureActive()
                            if (isReleased()) return@coroutineScope null
                            ShizukuCaptureProcessResult(process.exitValue(), output.await(), errors.await())
                        } finally {
                            // Close before coroutineScope joins blocked readers, also on timeout.
                            current.close()
                        }
                    }
                }
            }
            if (isReleased()) null else result
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            if (isReleased()) null else throw error
        } finally {
            owned?.close()
            synchronized(ownership) { if (active === owned) active = null }
        }
    }

    fun release() {
        val process = synchronized(ownership) { released = true; active }
        process?.close()
    }

    private fun isReleased(): Boolean = synchronized(ownership) { released }

    private class OwnedProcess(private val process: Process) {
        private val closed = AtomicBoolean(false)
        private var input: InputStream? = null
        private var errors: InputStream? = null
        private var output: OutputStream? = null
        val stdout get() = checkNotNull(input)
        val stderr get() = checkNotNull(errors)

        init {
            try {
                input = process.inputStream
                errors = process.errorStream
                output = process.outputStream
            } catch (error: Throwable) {
                close()
                throw error
            }
        }

        fun close() {
            if (!closed.compareAndSet(false, true)) return
            runCatching { process.destroy() }
            runCatching { input?.close() }
            runCatching { errors?.close() }
            runCatching { output?.close() }
        }
    }

    companion object {
        // Matches the raw decoder's 25M-pixel ceiling at four bytes per pixel plus header.
        const val MAX_FRAME_BYTES = 100_000_016
        private const val MAX_ERROR_BYTES = 8 * 1024
    }
}

/** Reads at most the limit plus one byte, rejecting excess instead of retaining or draining it. */
private class LimitedCaptureInput(
    private val source: InputStream,
    private val limit: Int,
    private val checkpoint: () -> Unit,
) : InputStream() {
    private var consumed = 0

    override fun read(): Int {
        checkpoint()
        val value = source.read()
        if (value >= 0) record(1)
        return value
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
        if (length == 0) return 0
        checkpoint()
        val count = source.read(buffer, offset, minOf(length, limit - consumed + 1))
        if (count > 0) record(count)
        return count
    }

    private fun record(count: Int) {
        consumed += count
        if (consumed > limit) throw IOException("Screen capture process output exceeds limit")
    }
}
