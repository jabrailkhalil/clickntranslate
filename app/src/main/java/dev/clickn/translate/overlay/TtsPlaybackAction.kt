// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.overlay

import dev.clickn.translate.tts.TtsPlaybackState
import kotlinx.coroutines.flow.StateFlow

data class TtsPlaybackAction(
    val playbackId: String,
    val playbackState: StateFlow<TtsPlaybackState>,
    val onToggle: (String) -> Unit,
    val onStart: (String) -> Unit,
)
