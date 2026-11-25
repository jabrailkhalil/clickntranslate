package dev.clickn.translate.overlay

import android.content.Context
import android.os.Looper
import android.view.MotionEvent
import android.view.View
import android.widget.FrameLayout
import java.io.Closeable
import java.util.WeakHashMap

/** Main-thread lease; closing it restores only windows still owned by the manager. */
interface SourceObservationLease : Closeable {
    /** At acquisition, at least one visible root was actually hidden. */
    val changedVisibility: Boolean
}

/** Independent suppression over each live root's latest application-requested visibility. */
internal class SourceCaptureVisibility<T : Any>(
    private val readVisibility: (T) -> Int,
    private val writeVisibility: (T, Int) -> Unit,
    private val visible: Int,
    private val suppressed: Int,
    private val checkThread: () -> Unit = {},
) {
    private val desired = WeakHashMap<T, Int>()
    private var leases = 0

    fun track(root: T, visibility: Int = readVisibility(root)) {
        checkThread()
        desired[root] = visibility
        apply(root, visibility)
    }

    fun setDesired(root: T, visibility: Int) {
        checkThread()
        if (!desired.containsKey(root)) return
        desired[root] = visibility
        apply(root, visibility)
    }

    fun untrack(root: T) {
        checkThread()
        desired.remove(root)
    }

    fun hideForSourceObservation(): SourceObservationLease {
        checkThread()
        val changed = desired.keys.any { readVisibility(it) == visible }
        leases++
        desired.forEach { (root, visibility) -> apply(root, visibility) }
        return object : SourceObservationLease {
            override val changedVisibility = changed
            private var closed = false
            override fun close() {
                checkThread()
                if (closed) return
                closed = true
                leases--
                if (leases == 0) desired.forEach { (root, visibility) -> apply(root, visibility) }
            }
        }
    }

    private fun apply(root: T, visibility: Int) {
        val actual = if (leases > 0 && visibility == visible) suppressed else visibility
        if (readVisibility(root) != actual) writeVisibility(root, actual)
    }
}

internal fun sourceCaptureViewVisibility() = SourceCaptureVisibility<View>(
    readVisibility = { it.visibility },
    writeVisibility = { view, visibility -> view.visibility = visibility },
    visible = View.VISIBLE,
    suppressed = View.INVISIBLE,
    checkThread = { check(Looper.myLooper() == Looper.getMainLooper()) { "Overlay visibility requires Main" } },
)

internal fun combineSourceObservationLeases(vararg leases: SourceObservationLease): SourceObservationLease =
    object : SourceObservationLease {
        override val changedVisibility = leases.any { it.changedVisibility }
        private var closed = false
        override fun close() {
            if (closed) return
            closed = true
            var failure: Throwable? = null
            leases.reversed().forEach { lease ->
                try { lease.close() }
                catch (caught: Throwable) {
                    if (failure == null) failure = caught else failure!!.addSuppressed(caught)
                }
            }
            failure?.let { throw it }
        }
    }

/** Observe touches without replacing native selection/scrolling or existing child listeners. */
internal class SourceObservationRoot(
    context: Context,
    private val onTouchActive: (Boolean) -> Unit,
) : FrameLayout(context) {
    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> onTouchActive(true)
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> onTouchActive(false)
        }
        return super.dispatchTouchEvent(event)
    }
}
