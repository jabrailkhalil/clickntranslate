package dev.clickn.translate.tts

import android.media.MediaExtractor
import android.media.MediaFormat
import android.os.Bundle
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

/** Uses installed, offline voices only. The synthetic speech is written to a file without playback. */
@RunWith(AndroidJUnit4::class)
class OfflineVoiceSynthesisTest {
    @Test fun englishVoiceProducesAudio() = synthesize("en-US", "The green door is open.")
    @Test fun russianVoiceProducesAudio() = synthesize("ru-RU", "Зелёная дверь открыта.")

    private fun synthesize(tag: String, text: String) {
        assumeTrue(InstrumentationRegistry.getArguments().getString("voiceFile") == "true")
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val initialized = CountDownLatch(1)
        var status = TextToSpeech.ERROR
        val engine = TextToSpeech(context) { result ->
            status = result
            initialized.countDown()
        }
        try {
            assertTrue("Speech engine initialization timed out", initialized.await(12, TimeUnit.SECONDS))
            assertEquals(TextToSpeech.SUCCESS, status)
            val voices = engine.voices.orEmpty().filter { voice ->
                voice.locale.language == tag.substringBefore('-') && !voice.isNetworkConnectionRequired &&
                    TextToSpeech.Engine.KEY_FEATURE_NOT_INSTALLED !in voice.features.orEmpty()
            }
            assumeTrue("No installed offline voice for $tag", voices.isNotEmpty())
            val preferred = orderedSystemTtsVoiceOptions(voices.map {
                SystemTtsVoiceOption(it.name, it.locale.toLanguageTag(), it.isNetworkConnectionRequired)
            }, tag).first().name
            assertEquals(TextToSpeech.SUCCESS, engine.setVoice(voices.first { it.name == preferred }))
            val completed = CountDownLatch(1)
            var succeeded = false
            engine.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(id: String) = Unit
                override fun onDone(id: String) {
                    if (id == tag) {
                        succeeded = true
                        completed.countDown()
                    }
                }
                @Deprecated("Required Android TTS callback")
                override fun onError(id: String) {
                    if (id == tag) completed.countDown()
                }
            })
            val directory = File(context.filesDir, "qa-tts")
            check(directory.isDirectory || directory.mkdirs())
            val output = File(directory, "$tag.wav")
            assertEquals(TextToSpeech.SUCCESS, engine.synthesizeToFile(text, Bundle(), output, tag))
            assertTrue("Speech engine did not finish $tag", completed.await(30, TimeUnit.SECONDS))
            assertTrue("Speech engine rejected $tag", succeeded)
            val media = MediaExtractor()
            try {
                media.setDataSource(output.absolutePath)
                assertEquals(1, media.trackCount)
                val format = media.getTrackFormat(0)
                assertTrue(format.getString(MediaFormat.KEY_MIME).orEmpty().startsWith("audio/"))
                assertTrue(format.getLong(MediaFormat.KEY_DURATION) > 200_000)
            } finally {
                media.release()
            }
        } finally {
            engine.shutdown()
        }
    }
}
