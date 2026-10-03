// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.download

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/** A confirmation belongs to one request, not whichever download happens to be current later. */
internal class ModelDownloadCancelConfirmation {
    private val pending = MutableStateFlow<String?>(null)
    val request = pending.asStateFlow()

    fun show(requestKey: String) { pending.value = requestKey }
    fun dismiss() { pending.value = null }

    fun consume(currentRequestKey: String?): Boolean {
        val requested = pending.value
        dismiss()
        return requested != null && requested == currentRequestKey
    }
}
