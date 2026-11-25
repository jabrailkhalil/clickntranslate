package dev.clickn.translate.ocr

import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext

/** A non-cancellable native Task may still read its borrowed pixels after its caller is cancelled. */
internal suspend fun <T> finishBorrowedOcrWork(work: suspend () -> T): T {
    currentCoroutineContext().ensureActive()
    val result = withContext(NonCancellable) { work() }
    // Retain the caller's resource lease until the Task drains, then reject obsolete output.
    currentCoroutineContext().ensureActive()
    return result
}
