// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

internal object TranslationLogElapsedPolicy {
    fun resolve(
        developerOptionsEnabled: Boolean,
        batchCumulativeCompletionTimeEnabled: Boolean,
        itemElapsedMs: Long?,
        batchElapsedMs: Long,
    ): Long {
        val safeBatchElapsedMs = batchElapsedMs.coerceAtLeast(0L)
        if (developerOptionsEnabled && batchCumulativeCompletionTimeEnabled) {
            return safeBatchElapsedMs
        }
        return itemElapsedMs?.coerceAtLeast(0L) ?: safeBatchElapsedMs
    }
}
