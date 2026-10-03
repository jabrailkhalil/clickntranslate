// Modified for Click'n'Translate on October 3, 2026.
package dev.clickn.translate.tts

import dev.clickn.translate.data.TtsProvider
import dev.clickn.translate.data.MAX_TTS_PLAYBACK_GAIN_DB
import dev.clickn.translate.data.MIN_TTS_PLAYBACK_GAIN_DB

internal fun normalizedTtsPlaybackGainDb(value: Int): Int =
    value.coerceIn(MIN_TTS_PLAYBACK_GAIN_DB, MAX_TTS_PLAYBACK_GAIN_DB)

internal fun ttsPlaybackGainMillibels(value: Int): Int =
    normalizedTtsPlaybackGainDb(value) * 100

internal fun supportsTtsPlaybackGain(provider: TtsProvider): Boolean =
    provider != TtsProvider.SYSTEM
