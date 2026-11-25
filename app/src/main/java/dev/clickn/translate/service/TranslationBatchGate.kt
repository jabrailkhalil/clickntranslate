// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.service

import dev.clickn.translate.capture.CaptureUiVisibility
import java.util.concurrent.atomic.AtomicReference

/** Allows overlay updates only from the currently active capture batch. */
internal class TranslationBatchGate(private val visibility: CaptureUiVisibility = CaptureUiVisibility()) {
    private data class Batch(val id: Long, val uiRevision: Long)
    private val activeBatch = AtomicReference<Batch?>(null)

    fun activate(batchId: Long, uiRevision: Long = visibility.snapshot().revision): Long? = activeBatch
        .getAndSet(Batch(batchId, uiRevision).takeIf { visibility.allowsPresentation(uiRevision) })?.id

    fun invalidate(): Long? = activeBatch.getAndSet(null)?.id

    fun accepts(batchId: Long?): Boolean = batchId != null && activeBatch.get()?.let {
        it.id == batchId && visibility.allowsPresentation(it.uiRevision)
    } == true
}
