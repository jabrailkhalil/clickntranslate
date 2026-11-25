package dev.clickn.translate.capture

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.*
import org.junit.Test

/** Tests the actual resource-owner relay; does not fake a platform MediaProjection or VD. */
class MediaProjectionLifetimeTest {
    @Test fun systemStopClosesResourcesBeforeNotifyingTheOwnerExactlyOnce() {
        val events = mutableListOf<String>()
        lateinit var lifetime: MediaProjectionLifetime
        lifetime = MediaProjectionLifetime({
            assertTrue(lifetime.isReleased)
            events += "resources"
        }, { events += "owner" })
        assertFalse(lifetime.isReleased)
        lifetime.systemStopped(); lifetime.systemStopped(); lifetime.release()
        assertEquals(listOf("resources", "owner"), events)
    }

    @Test fun normalOwnerReleaseSuppressesAnAlreadyQueuedPlatformStop() {
        var releases = 0; var notifications = 0
        val lifetime = MediaProjectionLifetime({ releases++ }, { notifications++ })
        lifetime.release(); lifetime.systemStopped(); lifetime.release()
        assertEquals(1, releases); assertEquals(0, notifications)
        assertTrue(lifetime.isReleased)
    }

    @Test fun resourceCleanupFailureStillNotifiesTheOwnerAndCannotReopenTheSession() {
        val failure = IllegalStateException("owned cleanup failure")
        var notifications = 0
        val lifetime = MediaProjectionLifetime({ throw failure }, { notifications++ })
        assertSame(failure, assertThrows(IllegalStateException::class.java) { lifetime.systemStopped() })
        assertTrue(lifetime.isReleased); assertEquals(1, notifications)
        lifetime.systemStopped(); lifetime.release()
        assertEquals(1, notifications)
    }

    @Test fun queuedServiceReleaseDuringSystemCallbackCannotDoubleCloseOrNotifyBeforeCleanup() {
        val entered = CountDownLatch(1); val finish = CountDownLatch(1)
        val releases = AtomicInteger(); val notifications = AtomicInteger()
        val callbackFailure = AtomicReference<Throwable>()
        val lifetime = MediaProjectionLifetime({
            releases.incrementAndGet(); entered.countDown()
            assertTrue(finish.await(5, TimeUnit.SECONDS))
        }, { notifications.incrementAndGet() })
        val callback = Thread {
            try { lifetime.systemStopped() }
            catch (failure: Throwable) { callbackFailure.set(failure) }
        }
        callback.start()
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            lifetime.release(); lifetime.systemStopped()
            assertTrue(lifetime.isReleased)
            assertEquals(1, releases.get()); assertEquals(0, notifications.get())
        } finally {
            finish.countDown(); callback.join(5_000)
        }
        assertFalse(callback.isAlive)
        assertNull("Callback failed", callbackFailure.get())
        assertEquals(1, releases.get()); assertEquals(1, notifications.get())
    }
}
