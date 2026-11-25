package dev.clickn.translate.dictionary

import android.os.CancellationSignal
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Consume and close every cursor/database inside [read]; a cursor must not escape this lifetime. */
internal suspend fun <T> cancellableDictionaryRead(read: (CancellationSignal) -> T): T = coroutineScope {
    val signal = CancellationSignal()
    val cancellation = launch(start = CoroutineStart.UNDISPATCHED) {
        try {
            awaitCancellation()
        } finally {
            signal.cancel()
        }
    }
    try {
        withContext(Dispatchers.IO) { read(signal) }
    } finally {
        withContext(NonCancellable) { cancellation.cancelAndJoin() }
    }
}
