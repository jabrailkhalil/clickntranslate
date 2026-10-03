// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.tts

import androidx.annotation.StringRes
import dev.clickn.translate.R
import dev.clickn.translate.data.TtsProvider

@StringRes
internal fun ttsPresetSummaryLabelRes(
    enabled: Boolean,
    provider: TtsProvider,
): Int {
    if (!enabled) return R.string.main_status_disabled
    return when (provider) {
        TtsProvider.SYSTEM -> R.string.settings_tts_provider_system
        TtsProvider.GENERIC_HTTP -> R.string.settings_tts_provider_generic_http
        TtsProvider.VOLCENGINE -> R.string.settings_tts_provider_volc
        TtsProvider.MINIMAX -> R.string.settings_tts_provider_minimax
        TtsProvider.MIMO -> R.string.settings_tts_provider_mimo
    }
}
