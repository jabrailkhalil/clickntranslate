# Android voice studio

These are new independent ElevenLabs and MiniMax account integrations. The original MiniMax voice-manager code, credentials, model wrappers and binaries are not reused. Each provider retains its own voice identifiers and account. MiniMax voices cannot be imported as ElevenLabs voices. System Android TTS and offline translation remain available without an account.

## Official contracts

The fixed origin is `https://api.elevenlabs.io`. Every request receives the key of the current profile's `CredentialIdentity.speech(settings.copy(speechProvider = ELEVENLABS))`. The client does not read a provider-wide key, store credentials, choose another endpoint, follow redirects or automatically retry a paid request.

| Action | Official API | Application behavior |
| --- | --- | --- |
| List personal account voices | [`GET /v2/voices`](https://elevenlabs.io/docs/api-reference/voices/search) | `voice_type=personal`, `page_size=30`, `include_total_count=false`; explicit next-page action follows `has_more` and `next_page_token`. Missing/repeated tokens fail. Up to 1000 records per screen session. Missing `is_owner` never grants deletion. |
| Clone selected recordings | [`POST /v1/voices/add`](https://elevenlabs.io/docs/api-reference/voices/ivc/create) | Multipart `name`, optional `description`, `remove_background_noise=false`, repeated `files` parts. Reads `voice_id` and `requires_verification`. No professional voice training or verification automation is implemented. |
| Generate design previews | [`POST /v1/text-to-voice/design`](https://elevenlabs.io/docs/api-reference/text-to-voice/design) | `eleven_multilingual_ttv_v2`, description 20–1000 characters, explicit text 100–1000 characters or `auto_generate_text=true`; `stream_previews=false`, `mp3_22050_32`. Returned base64 MP3 samples are available for local playback. |
| Save chosen design | [`POST /v1/text-to-voice`](https://elevenlabs.io/docs/api-reference/text-to-voice/create) | Explicit button submits `voice_name`, the original design description and only the chosen `generated_voice_id`. Voice selection for TTS remains a separate action. |
| Delete account voice | [`DELETE /v1/voices/{voice_id}`](https://elevenlabs.io/docs/api-reference/voices/delete) | Requires known ownership, an in-app confirmation and server `status=ok`. Deleting the selected voice clears its selection in the same credential scope. |

The official [IVC quickstart](https://elevenlabs.io/docs/eleven-api/guides/how-to/voices/instant-voice-cloning) documents the `files` collection; the reference page's generated cURL example spells its upload part `files[]`. The integration uses repeated `files` parts, matching the SDK form collection. Live multipart acceptance is pending paid-account verification.

## MiniMax adapter

The fixed origin is `https://api.minimax.io` and authentication is Bearer with the current profile's separate `SPEECH/MINIMAX` key. `VoiceStudioBackend` capabilities drive one shared studio/session, file preparation, credential checks and playback lifecycle. The adapters preserve the following API differences.

| Action | Official API | Behavior |
| --- | --- | --- |
| Personal list | [`POST /v1/get_voice`](https://platform.minimax.io/docs/api-reference/voice-management-get) | Sends `voice_type=all` and displays only account `voice_cloning` and `voice_generation` arrays. No invented page tokens. These voices can be absent until first successful TTS; freshly created IDs remain visible in the current session. |
| Upload + clone | [`POST /v1/files/upload`](https://platform.minimax.io/docs/api-reference/file-management-upload), then [`POST /v1/voice_clone`](https://platform.minimax.io/docs/api-reference/voice-cloning-clone) | One selected MP3/M4A/WAV, measured 10–300 seconds, up to the app's 10 MiB bound. Upload purpose is `voice_clone`; the returned numeric file ID and user-chosen valid 8–256-character voice ID go into clone JSON. No hidden paid preview or TTS activation. An unused clone can expire after 7 days. |
| Design | [`POST /v1/voice_design`](https://platform.minimax.io/docs/api-reference/voice-design-design) | The explicit **Create account voice + preview** button sends prompt and required preview text (1–500 characters). The operation immediately creates a real voice ID and returns hexadecimal preview audio. There is no separate Save endpoint or fake Save button. Local app prompt bounds are 20–1000 characters. |
| Delete | [`POST /v1/delete_voice`](https://platform.minimax.io/docs/api-reference/voice-management-delete) | After the shared confirmation, submits the account voice ID and its exact `voice_cloning` or `voice_generation` type. System voices cannot be deleted. Requires `base_resp.status_code=0`. |
| Speech | [`POST /v1/t2a_v2`](https://platform.minimax.io/docs/api-reference/speech-t2a-http) | Explicit speech action sends a documented model, nested voice/audio settings, `stream=false` and `output_format=hex`. Requires successful envelope and final `data.status=2`; validates ASCII hex before allocation, maximum 12 MiB MP3. Shared speech speed/pitch remain local playback controls. |

The TTS client allows only the eight model IDs currently listed by the official synchronous endpoint (`speech-2.8`, `speech-2.6`, `speech-02`, `speech-01`, each `hd`/`turbo`), with `speech-2.8-hd` as the UI default. It does not imply those models or cloning are enabled on a particular account. `base_resp` errors are failures even with HTTP 200; messages never echo provider response text.

Known uploaded source IDs created by the clone operation receive a best-effort [`POST /v1/files/delete`](https://platform.minimax.io/docs/api-reference/file-management-delete), bounded to 5 seconds. Unknown IDs after an interrupted upload cannot be removed automatically. Cleanup can fail after cancellation, key revocation or loss of connectivity; recordings may remain in the provider account under its retention policy and can be managed there. The app never lists or deletes unrelated account files.

## Local data and lifetime

- SAF selection only reads into a private temporary cache directory. It sends no network request and retains no URI grant. The review shows original display names and actual copied sizes before Create. Upload part filenames are generated locally; original names and paths are not uploaded.
- App limits are 5 recordings, 10 MiB each and 25 MiB total; these are application safeguards, not claims about the provider's maximum. Actual audio container signatures are checked for MP3, WAV, FLAC, OGG and M4A; server decoding still determines validity. Prefer clean, single-speaker audio. The [official guidance](https://elevenlabs.io/docs/help-center/product/voices/voice-cloning/what-files-do-you-accept-for-voice-cloning) recommends 1–2 minutes of good audio. The app does not certify recording quality or clone fidelity.
- Selected recordings require an explicit ownership/consent checkbox and Create. Description generation and saving are separate explicit actions. No sample voices belonging to other people are supplied by the app.
- Response JSON is bounded to 18 MiB; at most 5 previews, 4 MiB each and 12 MiB combined. Preview MP3 bytes remain in memory, with a private temporary FD-backed file only during playback. No preview URL supplied by the service is followed.
- Screen disposal or a credential/profile revision cancels work. A direct current-revision guard also runs before/after key access, immediately before actual HTTP execution, after responses, before publishing state and in MediaPlayer's prepared-to-start callback. This prevents new work and late publication while Compose disposal is pending. Stop/backgrounding cancels the current operation and releases preview audio focus/player/file. HTTP cancellation closes and drains the actual request before its multipart source files can be removed.
- A cancelled or failed creation can still have completed on the server. The UI blocks another creation until the user refreshes personal voices; the client never automatically repeats it. Provider errors are summarized without echoing response bodies, descriptions or keys.
- Voice slots, access, verification, account plan and geographical availability are controlled by ElevenLabs. A voice clone is stored in the provider account, not exported as a standalone model.

## Verification

`ElevenVoiceContractTest` uses a real local HTTPS MockWebServer and trusted test certificate to verify pagination, multipart fields, design/save/delete payloads, ownership, malformed IDs/audio, secret-safe errors, 401/403/429/5xx, cancellation with transport drain, refused redirects, direct credential invalidation and no retry after a paid POST disconnect. `VoiceStudioLimitsTest` checks streaming size/cancellation and audio signatures. `MiniMaxVoiceContractTest` checks upload/clone/own-source cleanup, immediate design, account-only list/delete, the TTS contract, strict hex limits, mandatory success envelopes, incomplete audio rejection and paid-call cancellation/no retries.

Standalone Kotlin/JUnit execution on 2026-10-25: **29 tests passed** (`.tmp/voice-studio-jvm-tests.log`). New `media/voices` sources also compile against Android 36 platform stubs. A central Android build, lint and device playback/UI checks are still pending for this addition. `VoicePreviewIntegrationTest` adds two actual MediaPlayer/FD/focus/credential-lifetime checks using generated silent PCM, without voice-account access.

No real paid account, voice-slot mutation, live cloning/design or paid speech has been exercised. Unauthenticated reachability discovery from this host returned regional restriction HTML from ElevenLabs; MiniMax `GET /v1/models` returned HTTP 401 JSON `authorized_error/1004`. GET on MiniMax's POST-only voice routes returned 404; this does **not** establish an account's voice entitlement, billing, regional eligibility or successful API behavior. No access workaround and no paid POST was attempted.
