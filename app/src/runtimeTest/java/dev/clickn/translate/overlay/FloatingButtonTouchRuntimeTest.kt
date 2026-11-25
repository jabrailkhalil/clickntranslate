package dev.clickn.translate.overlay

import android.os.Looper
import android.os.SystemClock
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.ViewGroup
import android.view.WindowManager
import androidx.test.core.app.ApplicationProvider
import dev.clickn.translate.ClickTranslateApp
import dev.clickn.translate.R
import dev.clickn.translate.data.CompanionPrefs
import dev.clickn.translate.data.FloatingSkill
import java.time.Duration
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import org.robolectric.annotation.LooperMode

/** Real View dispatch, WindowManager attachment and paused main-queue deadlines; no menu hook. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], application = ClickTranslateApp::class, qualifiers = "w480dp-h1000dp-mdpi")
@LooperMode(LooperMode.Mode.PAUSED)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
class FloatingButtonTouchRuntimeTest {
    private val app get() = ApplicationProvider.getApplicationContext<ClickTranslateApp>()
    private val holdMs get() = ViewConfiguration.getLongPressTimeout().toLong()
    private val doubleTapMs get() = ViewConfiguration.getDoubleTapTimeout().toLong()

    @Test fun cancelNeverBecomesTapOrMenuEvenIfAnUpArrivesLater() = withButton { h ->
        val target = h.button
        val down = send(target, MotionEvent.ACTION_DOWN)
        send(target, MotionEvent.ACTION_CANCEL, down)
        idle(holdMs + 20)
        send(target, MotionEvent.ACTION_UP, down)
        assertEquals(0, h.taps)
        assertEquals(0, h.doubleTaps)
        assertNull(h.menu)

        // Cancellation did not disable the next independent gesture.
        tap(target)
        assertEquals(1, h.taps)
    }

    @Test fun heldCurrentButtonOpensRealMenuAndReleaseDoesNotAlsoTap() = withButton { h ->
        val target = h.button
        val down = send(target, MotionEvent.ACTION_DOWN)
        idle(holdMs + 20)
        val menu = requireNotNull(h.menu)
        assertTrue(menu.isAttachedToWindow)
        val loop = requireNotNull(findDescription(menu, target.context.getString(R.string.menu_loop_translate)))
        assertTrue(loop.isClickable)
        send(target, MotionEvent.ACTION_UP, down)
        assertEquals(0, h.taps)
        assertSame(menu, h.menu)
        assertTrue(loop.performClick())
        assertEquals(1, h.loopSelections)
        assertNull(h.menu)
    }

    @Test fun dragMovesTheWindowAndSuppressesBothHoldAndTap() = withButton { h ->
        val target = h.button
        val beforeX = h.params.x
        val down = send(target, MotionEvent.ACTION_DOWN)
        val distance = ViewConfiguration.get(app).scaledTouchSlop * 3f + 10f
        send(target, MotionEvent.ACTION_MOVE, down, x = 20f + distance)
        assertEquals(beforeX + distance.toInt(), h.params.x)
        idle(holdMs + 20)
        send(target, MotionEvent.ACTION_UP, down, x = 20f + distance)
        assertEquals(0, h.taps)
        assertEquals(0, h.doubleTaps)
        assertNull(h.menu)
    }

    @Test fun hideAndRecreationInvalidateTheOldHoldAndAccessibilityCallbacks() = withButton { h ->
        val old = h.button
        send(old, MotionEvent.ACTION_DOWN)
        h.manager.hide()
        // WindowManager.removeView retires the manager synchronously but detaches asynchronously.
        // Old accessibility callbacks must already be inert while that removal is still queued.
        old.performClick()
        old.performLongClick()
        assertEquals(0, h.taps)
        assertNull(h.menu)
        shadowOf(Looper.getMainLooper()).idle()
        assertFalse(old.isAttachedToWindow)
        h.manager.show()
        idle(holdMs + 20)
        assertNotSame(old, h.button)
        assertNull("An old target must not open a menu on the new button", h.menu)
        old.performClick()
        old.performLongClick()
        assertEquals(0, h.taps)
        assertNull(h.menu)
        val current = h.button
        val down = send(current, MotionEvent.ACTION_DOWN)
        idle(holdMs + 20)
        assertNotNull(h.menu)
        send(current, MotionEvent.ACTION_UP, down)
        assertEquals(0, h.taps)
    }

    @Test fun windowDetachmentCancelsHoldEvenWhenTheSameViewIsReattached() = withButton { h ->
        val target = h.button
        val params = h.params
        val wm = app.getSystemService(WindowManager::class.java)
        val down = send(target, MotionEvent.ACTION_DOWN)
        wm.removeViewImmediate(target)
        assertFalse(target.isAttachedToWindow)
        wm.addView(target, params)
        idle(holdMs + 20)
        assertTrue(target.isAttachedToWindow)
        assertNull("Reattachment must not revive a held gesture from the old attachment", h.menu)
        send(target, MotionEvent.ACTION_UP, down)
        assertEquals(0, h.taps)
        val freshDown = send(target, MotionEvent.ACTION_DOWN)
        idle(holdMs + 20)
        assertNotNull(h.menu)
        send(target, MotionEvent.ACTION_UP, freshDown)
        assertEquals(0, h.taps)
    }

    @Test fun temporaryCaptureHidingDoesNotReviveAHoldAfterVisibilityReturns() = withButton { h ->
        val target = h.button
        val down = send(target, MotionEvent.ACTION_DOWN)
        assertTrue(h.manager.setHiddenForCapture(true))
        assertEquals(View.INVISIBLE, target.visibility)
        assertTrue(h.manager.setHiddenForCapture(false))
        idle(holdMs + 20)
        send(target, MotionEvent.ACTION_UP, down)
        assertNull(h.menu)
        assertEquals(0, h.taps)
        tap(target)
        assertEquals(1, h.taps)
    }

    @Test fun inputModeKeepsDelayedSingleAndDoubleTapButCancelDoesNotCountAsASecondTap() = withButton { h ->
        h.manager.skill = FloatingSkill.INPUT_TRANSLATE
        val target = h.button
        tap(target)
        assertEquals(0, h.taps)
        idle(doubleTapMs + 20)
        assertEquals(1, h.taps)
        tap(target)
        tap(target)
        assertEquals(1, h.doubleTaps)
        idle(doubleTapMs + 20)
        assertEquals(1, h.taps)

        tap(target)
        val down = send(target, MotionEvent.ACTION_DOWN)
        send(target, MotionEvent.ACTION_CANCEL, down)
        idle(doubleTapMs + 20)
        assertEquals("Only the earlier completed tap may run", 2, h.taps)
        assertEquals(1, h.doubleTaps)
        assertNull(h.menu)
    }

    @Test fun hidingTheButtonCancelsAnInputSingleTapWaitingForDoubleTap() = withButton { h ->
        h.manager.skill = FloatingSkill.INPUT_TRANSLATE
        tap(h.button)
        h.manager.hide()
        h.manager.show()
        idle(doubleTapMs + 20)
        assertEquals(0, h.taps)
        assertEquals(0, h.doubleTaps)
        assertNull(h.menu)
    }

    private class Harness(val manager: FloatingButtonManager) {
        var taps = 0
        var doubleTaps = 0
        var loopSelections = 0
        val button get() = field("view") as View
        val params get() = field("layoutParams") as WindowManager.LayoutParams
        val menu get() = field("arcMenuView") as? View
        private fun field(name: String): Any? = FloatingButtonManager::class.java.getDeclaredField(name)
            .apply { isAccessible = true }.get(manager)
    }

    private fun withButton(block: (Harness) -> Unit) {
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        lateinit var h: Harness
        val manager = FloatingButtonManager(app, { h.taps++ }, { h.doubleTaps++ },
            { h.loopSelections++ }, app.settingsRepository, scope)
        h = Harness(manager)
        try {
            CompanionPrefs.setKeepVisible(app, true)
            manager.initialX = 100
            manager.initialY = 400
            manager.snapToEdgeEnabled = false
            manager.autoDockEnabled = false
            manager.show()
            shadowOf(Looper.getMainLooper()).idle()
            assertTrue("Test must dispatch to an attached real button", h.button.isAttachedToWindow)
            block(h)
        } finally {
            manager.hide()
            scope.cancel()
        }
    }

    private fun send(target: View, action: Int, downTime: Long = SystemClock.uptimeMillis(),
                     x: Float = 20f, y: Float = 20f): Long {
        val event = MotionEvent.obtain(downTime, SystemClock.uptimeMillis(), action, x, y, 0)
        try {
            assertTrue("Actual button should consume action $action", target.dispatchTouchEvent(event))
        } finally {
            event.recycle()
        }
        return downTime
    }

    private fun tap(target: View) {
        val down = send(target, MotionEvent.ACTION_DOWN)
        send(target, MotionEvent.ACTION_UP, down)
    }

    private fun idle(ms: Long) = shadowOf(Looper.getMainLooper()).idleFor(Duration.ofMillis(ms))

    private fun findDescription(view: View, description: String): View? {
        if (view.contentDescription?.toString() == description) return view
        if (view is ViewGroup) for (i in 0 until view.childCount) {
            findDescription(view.getChildAt(i), description)?.let { return it }
        }
        return null
    }
}
