# New Android speech implementation

`Speech(context[, secrets])` retains the original two-argument `speak(text,language)` entry point for
system speech and adds `speak(text,language,settings)`. Its `StateFlow<SpeechState>` exposes engine
readiness, system voices, pending playback and errors. Stop on lifecycle `ON_STOP` or route changes;
close the owner on disposal. `VoiceOptions` performs this lifecycle management for its preview instance.

System TTS lists engine voices and their language, network and installation flags. Automatic selection
uses an installed **offline** voice of the requested language. It never falls back silently to a network
voice or starts downloading voice data. A user can explicitly select a network voice; the UI labels it.
The voice installation button opens the platform TTS installation activity. Rate/pitch, language mismatch,
queue errors and asynchronous utterance failures are handled. Sentence/word chunks preserve Unicode
surrogate pairs and respect the platform input length. Old utterance callbacks cannot overwrite the
new request state. User input is limited to 64000 characters per system request.

Cloud speech is explicit: select OpenAI Speech or ElevenLabs, configure a model/voice and separately
stored speech API key, then tap Listen. No speech text, voice catalog or audio is sent/downloaded on
startup or on a provider change. The UI identifies AI-generated audio and possible provider charges.
The cloud endpoints are fixed to the official origins, use TLS, disable redirects and never reuse a
translation/OCR API key. Existing custom account voice IDs are accepted. This app does **not** create
a cloned voice from text, upload reference voice recordings or perform voice training.

- OpenAI: `POST https://api.openai.com/v1/audio/speech` with `model`, `input`, `voice` and
  `response_format=mp3`; built-in voices are strings and existing `voice_…` IDs use `{ "id": … }`.
- ElevenLabs: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128`
  with `xi-api-key`, `text` and `model_id`.

Cloud input is capped at 12000 characters and processed sequentially in sentence-aware segments of
at most 3800 UTF-8 bytes. Each segment has a 60-second HTTP timeout and a 12-MiB response limit checked
both from headers and while streaming. Unsupported MIME types and HTTP failures produce bounded
messages without echoing provider error bodies. Paid synthesis requests are never automatically retried.
Only one clip is downloaded/played at a time, and audio remains in private `cacheDir/speech-audio`.
Cancellation stops the HTTP call and media player; clip files are deleted after completion/failure/
cancellation. Startup removes orphaned clips from a previous process. OS process termination can leave
a cache file until the next startup; Android can also reclaim cache storage. Audio is never exported
automatically. Decoder preparation times out after 20 seconds and playback after five minutes per clip.
Speed/pitch adjust cloud playback locally. Audio focus loss stops speech.

Secrets use a separate `SPEECH_<provider>` Keystore/AES-GCM namespace. Settings export contains only
provider/model/voice/rate/pitch and never keys. Providers may retain submitted text according to the
account’s own service terms; no account-level zero-retention capability is promised.

Tests: `CloudSpeechClientTest` uses a local MockWebServer for both official wire contracts, Unicode text,
custom voice IDs, namespace-specific headers, cancellation, chunked response limits, error redaction
and invalid input without requests. `SystemSpeechIntegrationTest` requires an actual Android TTS engine
with installed offline data and explicitly records a JUnit skip if absent. A successful mock test is not
proof of live account entitlement, real voice quality, paid API availability or audible device playback.
Real paid synthesis remains unverified unless a separately authorized account test is run.

Official references checked during implementation:
[OpenAI Speech](https://developers.openai.com/api/reference/resources/audio/subresources/speech/methods/create),
[ElevenLabs Speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert),
[Android TextToSpeech](https://developer.android.com/reference/android/speech/tts/TextToSpeech).
