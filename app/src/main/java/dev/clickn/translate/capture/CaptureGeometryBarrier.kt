package dev.clickn.translate.capture

/**
 * Geometry is a lifetime of capture work, independent of the coroutine running the polling loop.
 * The first observation establishes a baseline; only subsequent, valid size changes retire work.
 */
internal class CaptureGeometryBarrier {
    private data class Size(val width: Int, val height: Int)
    private data class Batch(val id: Long, val generation: Long)

    private var displaySize: Size? = null
    private var captureSize: Size? = null
    private var generation = 0L
    private var batch: Batch? = null

    @Synchronized
    fun snapshot(): Long = generation

    /** Retires pixels and queued work when ownership changes even if dimensions stay equal. */
    @Synchronized
    fun retire(onRetired: () -> Unit = {}) {
        generation++
        batch = null
        onRetired()
    }

    @Synchronized
    fun isCurrent(expected: Long): Boolean = expected == generation

    @Synchronized
    fun observeDisplay(width: Int, height: Int, onChanged: () -> Unit = {}): Boolean =
        observe(width, height, display = true, onChanged)

    @Synchronized
    fun observeCapture(width: Int, height: Int, onChanged: () -> Unit = {}): Boolean =
        observe(width, height, display = false, onChanged)

    @Synchronized
    fun bindBatch(id: Long, expected: Long): Boolean {
        if (expected != generation) return false
        batch = Batch(id, expected)
        return true
    }

    @Synchronized
    fun acceptsBatch(id: Long?): Boolean =
        id != null && batch?.let { it.id == id && it.generation == generation } == true

    private fun observe(width: Int, height: Int, display: Boolean, onChanged: () -> Unit): Boolean {
        if (width <= 0 || height <= 0) return false
        val next = Size(width, height)
        val previous = if (display) displaySize else captureSize
        if (display) displaySize = next else captureSize = next
        if (previous == null || previous == next) return false
        generation++
        batch = null
        // The owner's short, non-suspending retirement precedes any new batch admission.
        // It must not perform I/O or wait for the cancelled worker.
        onChanged()
        return true
    }
}
