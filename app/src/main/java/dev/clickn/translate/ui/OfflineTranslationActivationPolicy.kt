package dev.clickn.translate.ui

import dev.clickn.translate.data.Settings
import dev.clickn.translate.data.TranslationSelectionSnapshot
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

/** Downloaded models stay useful even when a later provider/language choice prevents activation. */
internal object OfflineTranslationActivationPolicy {
    suspend fun downloadAndActivate(
        baseline: TranslationSelectionSnapshot,
        requestedPair: Settings,
        download: suspend () -> Unit,
        activate: suspend (TranslationSelectionSnapshot, Settings) -> Unit,
    ) {
        download()
        currentCoroutineContext().ensureActive()
        // The repository compares this original revision in the same transaction as activation.
        activate(baseline, requestedPair)
    }
}
