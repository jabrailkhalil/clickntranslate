package dev.clickn.translate.capture

import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.*
import org.junit.Test

class ShizukuCaptureProcessRunnerTest {
    @Test(timeout = 5_000) fun binaryOutputAndErrorAreDrainedBeforeDisposingTheRemoteProcess() = runBlocking {
        val bytes = byteArrayOf(0, 1, -1, 0, 127)
        val process = RemoteProcess(FinitePipe(bytes), FinitePipe("vendor failure".toByteArray()), exitCode = 7)
        process.finished.set(true)
        val result = runner().execute({ process }) { it.readBytes() }
        assertEquals(7, result?.exitCode)
        assertArrayEquals(bytes, result?.output)
        assertEquals("vendor failure", result?.error)
        assertTrue(process.successfulWait.get())
        assertDisposed(process)
    }

    @Test(timeout = 5_000) fun deadlineDestroysAChildWhoseStdoutAndStderrAreBothBlocked() = runBlocking {
        val stdout = BlockingPipe()
        val stderr = BlockingPipe()
        val process = RemoteProcess(stdout, stderr)
        val result = async { runner().execute({ process }, timeoutMillis = 500) { it.readBytes() } }
        withTimeout(2_000) { stdout.started.await(); stderr.started.await() }
        assertNull(withTimeout(2_000) { result.await() })
        assertDisposed(process)
    }

    @Test(timeout = 5_000) fun cancellationClosesBlockedPipesAndDoesNotReturnAFrame() = runBlocking {
        val stdout = BlockingPipe()
        val stderr = BlockingPipe()
        val process = RemoteProcess(stdout, stderr)
        var returned = false
        val capture = launch {
            runner().execute({ process }) { it.readBytes() }
            returned = true
        }
        withTimeout(2_000) { stdout.started.await(); stderr.started.await(); capture.cancelAndJoin() }
        assertTrue(capture.isCancelled)
        assertFalse(returned)
        assertDisposed(process)
    }

    @Test(timeout = 5_000) fun releaseUnblocksTheCurrentCommandAndRejectsFutureCommands() = runBlocking {
        val stdout = BlockingPipe()
        val stderr = BlockingPipe()
        val process = RemoteProcess(stdout, stderr)
        val owner = runner()
        val capture = async { owner.execute({ process }) { it.readBytes() } }
        withTimeout(2_000) { stdout.started.await(); stderr.started.await() }
        owner.release()
        assertNull(withTimeout(2_000) { capture.await() })
        assertNull(owner.execute({ error("Released runner must not create another child") }) { it.readBytes() })
        owner.release()
        assertDisposed(process)
    }

    @Test(timeout = 5_000) fun stdoutAndStderrLimitsAbortWithoutReadingPastOneExcessByte() = runBlocking {
        for (overflowOnStderr in listOf(false, true)) {
            val overflow = FinitePipe(ByteArray(20_000) { 42 })
            val process = if (overflowOnStderr) RemoteProcess(stderr = overflow) else RemoteProcess(stdout = overflow)
            val failure = runCatching {
                runner().execute({ process }, maxOutputBytes = 32) { it.readBytes() }
            }.exceptionOrNull()
            assertTrue("Oversized pipe must fail rather than truncate", failure is IOException)
            assertEquals(if (overflowOnStderr) 8_193 else 33, overflow.bytesRead.get())
            assertDisposed(process)
        }
    }

    @Test(timeout = 5_000) fun releaseDuringCreationDisposesTheChildBeforeItCanBeRead() = runBlocking {
        val creating = CompletableDeferred<Unit>()
        val finishCreation = CountDownLatch(1)
        val process = RemoteProcess()
        val owner = runner()
        val capture = async {
            owner.execute(createProcess = {
                creating.complete(Unit)
                check(finishCreation.await(2, TimeUnit.SECONDS))
                process
            }) { it.readBytes() }
        }
        try {
            withTimeout(2_000) { creating.await() }
            owner.release()
        } finally { finishCreation.countDown() }
        assertNull(withTimeout(2_000) { capture.await() })
        assertEquals(0, (process.stdout as FinitePipe).bytesRead.get())
        assertDisposed(process)
    }

    private fun runner() = ShizukuCaptureProcessRunner { child, timeout ->
        (child as RemoteProcess).waitRemote(timeout)
    }

    private fun assertDisposed(process: RemoteProcess) {
        assertEquals("Process must have exactly one owner", 1, process.destroys.get())
        assertTrue("stdout must be closed explicitly", process.stdout.closed.get())
        assertTrue("stderr must be closed explicitly", process.stderr.closed.get())
        assertTrue("stdin must be closed explicitly", process.stdin.closed.get())
    }

    private abstract class TestPipe : InputStream() {
        val closed = AtomicBoolean(false)
        override fun close() { closed.set(true) }
    }

    private class FinitePipe(bytes: ByteArray) : TestPipe() {
        private val source = ByteArrayInputStream(bytes)
        val bytesRead = AtomicInteger()
        override fun read(): Int = source.read().also { if (it >= 0) bytesRead.incrementAndGet() }
        override fun read(buffer: ByteArray, offset: Int, length: Int): Int =
            source.read(buffer, offset, length).also { if (it > 0) bytesRead.addAndGet(it) }
    }

    private class BlockingPipe : TestPipe() {
        val started = CompletableDeferred<Unit>()
        private val unblocked = CountDownLatch(1)
        override fun read(): Int {
            started.complete(Unit)
            check(unblocked.await(2, TimeUnit.SECONDS)) { "Pipe reader was not closed by its owner" }
            return -1
        }
        override fun close() { super.close(); unblocked.countDown() }
    }

    private class TrackingOutput : ByteArrayOutputStream() {
        val closed = AtomicBoolean(false)
        override fun close() { closed.set(true); super.close() }
    }

    /** Destroy deliberately does NOT close pipes: the runner must release each resource itself. */
    private class RemoteProcess(
        val stdout: TestPipe = FinitePipe(byteArrayOf()),
        val stderr: TestPipe = FinitePipe(byteArrayOf()),
        private val exitCode: Int = 0,
    ) : Process() {
        val stdin = TrackingOutput()
        val finished = AtomicBoolean(false)
        val successfulWait = AtomicBoolean(false)
        val destroys = AtomicInteger()
        override fun getInputStream() = stdout
        override fun getErrorStream() = stderr
        override fun getOutputStream() = stdin
        override fun waitFor(): Int = error("Unbounded wait must never be used")
        override fun exitValue(): Int {
            check(successfulWait.get()) { "exitValue cannot be polled before remote completion" }
            return exitCode
        }
        fun waitRemote(timeout: Long): Boolean {
            check(timeout in 1..100)
            Thread.sleep(minOf(10L, timeout))
            return finished.get().also { if (it) successfulWait.set(true) }
        }
        override fun destroy() { destroys.incrementAndGet() }
    }
}
