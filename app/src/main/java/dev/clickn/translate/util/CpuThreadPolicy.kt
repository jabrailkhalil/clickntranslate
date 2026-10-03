// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.util

internal object CpuThreadPolicy {
    const val MAX_INFERENCE_THREADS = 6

    fun select(availableProcessors: Int): Int = when (availableProcessors.coerceAtLeast(1)) {
        1 -> 1
        2 -> 2
        in 3..4 -> 2
        in 5..6 -> 4
        else -> MAX_INFERENCE_THREADS
    }

    fun availableProcessors(): Int = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)

    fun current(): Int = select(availableProcessors())
}
