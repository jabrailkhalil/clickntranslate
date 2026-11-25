package dev.clickn.translate.capture

internal data class CaptureUiVisibilitySnapshot(val visible: Boolean = false, val revision: Long = 0L)

/** In-process ownership only. No Activity/Context, Accessibility or Usage Access is retained. */
internal class CaptureUiVisibility {
    private val lock = Any()
    private val owners = mutableSetOf<Any>()
    private val observers = mutableSetOf<() -> Unit>()
    @Volatile private var current = CaptureUiVisibilitySnapshot()

    fun snapshot(): CaptureUiVisibilitySnapshot = current

    fun allowsPresentation(expectedRevision: Long): Boolean = current.let {
        !it.visible && it.revision == expectedRevision
    }

    fun started(owner: Any) = change(owner, started = true)
    fun stopped(owner: Any) = change(owner, started = false)

    /** Lifecycle callers run on Main, so removal of existing windows completes synchronously. */
    fun observe(observer: () -> Unit): () -> Unit {
        synchronized(lock) { observers.add(observer) }
        observer()
        return { synchronized(lock) { observers.remove(observer) }; Unit }
    }

    private fun change(owner: Any, started: Boolean) {
        val notify = synchronized(lock) {
            if (started) owners.add(owner) else owners.remove(owner)
            val visible = owners.isNotEmpty()
            if (visible == current.visible) return
            current = CaptureUiVisibilitySnapshot(visible, current.revision + 1L)
            observers.toList()
        }
        notify.forEach { it() }
    }
}

internal val MainCaptureUiVisibility = CaptureUiVisibility()
