package dev.clickn.translate.capture

import java.util.concurrent.ConcurrentLinkedDeque
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.job
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/** Exercises the production frame waiter with owned, timestamped buffer stand-ins. */
class LatestFrameFreshnessTest {
    @Test
    fun rejectsBufferedFrameAndAcceptsFreshFrameQueuedDuringListenerRegistration() = runBlocking {
        val stale = Frame(99)
        val fresh = Frame(101)
        val source = Source().apply {
            frames += stale
            afterRegistration = { frames += fresh }
        }

        val result = awaitFresh(source)

        assertSame(fresh, result)
        assertEquals(1, stale.closes.get())
        assertEquals(0, fresh.closes.get())
        assertNull(source.listener)
    }

    @Test
    fun equalTimestampAndRepeatedOldFramesAreClosedWhileWaitingForStrictlyNewerFrame() = runBlocking {
        val source = Source()
        var result: Frame? = null
        val wait = launch(start = CoroutineStart.UNDISPATCHED) { result = awaitFresh(source) }
        val rejected = listOf(Frame(100), Frame(80), Frame(100))
        rejected.forEach {
            source.frames += it
            source.listener!!.invoke()
            assertTrue(wait.isActive)
            assertNotNull(source.listener)
        }
        val fresh = Frame(101)
        source.frames += fresh
        source.listener!!.invoke()
        wait.join()

        assertSame(fresh, result)
        rejected.forEach { assertEquals(1, it.closes.get()) }
        assertEquals(0, fresh.closes.get())
        assertNull(source.listener)
    }

    @Test
    fun freshWaitTimeoutDoesNotFallBackToFrameQueuedWhileDetachingListener() = runBlocking {
        val boundary = Frame(101)
        val source = Source().apply { afterDetach = { frames += boundary } }

        assertNull(awaitFresh(source, timeoutMs = 20))

        assertNull(source.listener)
        assertSame(boundary, source.frames.peekLast())
        assertEquals(0, boundary.closes.get())
    }

    @Test
    fun optionalLegacyFinalDrainStillAppliesTheAcceptancePredicate() = runBlocking {
        val stale = Frame(100)
        val source = Source().apply { afterDetach = { frames += stale } }

        val result = awaitLatestFrame(
            source, timeoutMs = 20, closeUndelivered = Frame::close,
            acceptFrame = { it.timestamp > 100 }, finalDrainOnTimeout = true,
        )

        assertNull(result)
        assertEquals(1, stale.closes.get())
        assertNull(source.listener)
    }

    @Test
    fun callerCancellationDetachesAndQueuedOldCallbackCannotStealNextCapturesFrame() = runBlocking {
        val source = Source()
        val wait = launch(start = CoroutineStart.UNDISPATCHED) { awaitFresh(source) }
        val queuedCallback = source.listener!!
        wait.cancel()
        wait.join()
        val next = Frame(101)
        source.frames += next

        queuedCallback()

        assertNull(source.listener)
        assertSame(next, source.frames.peekLast())
        assertEquals(0, next.closes.get())
    }

    @Test
    fun cancellationDuringListenerInstallationCannotLeaveAnAttachedListener() = runBlocking {
        val source = Source()
        var resultWasDelivered = false
        val wait = launch(start = CoroutineStart.UNDISPATCHED) {
            val owner: Job = coroutineContext.job
            source.beforeRegistration = { owner.cancel() }
            awaitFresh(source)
            resultWasDelivered = true
        }
        wait.join()

        assertTrue(wait.isCancelled)
        assertFalse(resultWasDelivered)
        assertNull(source.listener)
    }

    @Test
    fun cancellationAfterResumeBeforeDispatchClosesTheUndeliveredImageExactlyOnce() = runBlocking {
        val dispatcher = QueuedDispatcher()
        val source = Source()
        var resultWasDelivered = false
        val wait = launch(dispatcher, start = CoroutineStart.UNDISPATCHED) {
            awaitFresh(source)
            resultWasDelivered = true
        }
        val fresh = Frame(101)
        source.frames += fresh
        source.listener!!.invoke()
        assertNull(source.listener)
        assertEquals(0, fresh.closes.get())

        wait.cancel()
        dispatcher.runQueued()
        wait.join()

        assertFalse(resultWasDelivered)
        assertEquals(1, fresh.closes.get())
        assertNull(source.listener)
    }

    @Test
    fun simultaneousCallbacksDeliverOneImageAndCloseTheLosingAcquisition() = runBlocking {
        val source = Source()
        var delivered: Frame? = null
        val wait = launch(start = CoroutineStart.UNDISPATCHED) { delivered = awaitFresh(source) }
        val callback = source.listener!!
        val acquired = CountDownLatch(2)
        source.afterAcquire = {
            acquired.countDown()
            check(acquired.await(2, TimeUnit.SECONDS)) { "Second callback did not acquire" }
        }
        val frames = listOf(Frame(101), Frame(102))
        source.frames.addAll(frames)
        val failure = AtomicReference<Throwable?>()
        val callbacks = List(2) {
            Thread {
                try { callback() }
                catch (caught: Throwable) { failure.compareAndSet(null, caught) }
            }.apply { start() }
        }
        callbacks.forEach { it.join(3_000) }
        assertTrue(callbacks.all { !it.isAlive })
        assertNull(failure.get())
        wait.join()

        assertTrue(frames.any { it === delivered })
        frames.forEach { assertEquals(if (it === delivered) 0 else 1, it.closes.get()) }
        assertNull(source.listener)
    }

    private suspend fun awaitFresh(source: Source, timeoutMs: Long = 5_000): Frame? =
        awaitLatestFrame(
            source, timeoutMs = timeoutMs, closeUndelivered = Frame::close,
            acceptFrame = { it.timestamp > 100 }, finalDrainOnTimeout = false,
        )

    private class Frame(val timestamp: Long) {
        val closes = AtomicInteger()
        fun close() { closes.incrementAndGet() }
    }

    private class Source : LatestFrameSource<Frame> {
        val frames = ConcurrentLinkedDeque<Frame>()
        @Volatile var listener: (() -> Unit)? = null
            private set
        var beforeRegistration: (() -> Unit)? = null
        var afterRegistration: (() -> Unit)? = null
        var afterDetach: (() -> Unit)? = null
        var afterAcquire: (() -> Unit)? = null

        override fun acquireLatest(): Frame? = frames.pollLast()?.also { afterAcquire?.invoke() }

        override fun setOnFrameAvailableListener(listener: (() -> Unit)?) {
            if (listener != null) beforeRegistration?.invoke()
            this.listener = listener
            if (listener == null) {
                afterDetach?.also { afterDetach = null }?.invoke()
            } else {
                afterRegistration?.also { afterRegistration = null }?.invoke()
            }
        }
    }

    private class QueuedDispatcher : CoroutineDispatcher() {
        private val queued = ConcurrentLinkedQueue<Runnable>()
        override fun dispatch(context: CoroutineContext, block: Runnable) { queued += block }
        fun runQueued() {
            while (true) (queued.poll() ?: return).run()
        }
    }
}
