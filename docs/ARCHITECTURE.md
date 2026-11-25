> Historical rewrite record through 1d17a83. The owner subsequently authorized restoration of the archived interface and working modules. Current source provenance and scope: [Android restoration](ANDROID_ARCHIVE_RESTORATION.ru.md). This document is not a description of the restored runtime.

# Independent Android implementation

The application has one Android module and a small manual application graph. Its source lives only under `dev.clickn.translate.next`; the stable production application ID remains `dev.clickn.translate`. No legacy application class, JNI bridge, precompiled application library, resource layout or module participates in the build.

## Boundaries

| Package | Responsibility |
| --- | --- |
| `core` | Immutable settings, language/provider choices, normalized capture region and exchange records. No Android dependencies. |
| `capture` | Consent-bound MediaProjection session or explicitly enabled Accessibility screenshots, shared FrameSource, overlays, region interaction, visual comparison and result generations. |
| `engine` | OCR documents and geometry, paragraph assembly, translator adapters, cancellable HTTP, UTF-8 partitioning, caches, glossary protection and optional manga grouping. |
| `local` / `cpp` | Private hash-addressed GGUF imports and one serialized CPU llama.cpp runtime, independently written JNI ownership and cancellation. |
| `store` | Room history, Paging, Unicode search index, dictionaries/corrections, atomic DataStore settings, authenticated Keystore secrets and explicit read-only legacy transfer. |
| `media` | Single-snapshot bounded URI decoding, EXIF/mirror correction, paragraph-aware PNG export and local/cloud TTS lifecycle. |
| `ui` | Material 3 screens, six-language labels, activity-independent ViewModel, navigation, SAF exports/imports. |
| `explanation` | Expiring original-word/context review, explicit selected-provider request, scoped credentials and a secure memory-only host. |

## Screen processing

1. The first screen asks for the target language and offers screen translation, a text trial or direct OCR. The immutable session purpose selects preparation: TRANSLATE validates the selected translator and OCR; RECOGNIZE touches only OCR configuration/models, never translation credentials, its model registry or automatic MT. Permission admission stages survive activity recreation without duplicating a session.
2. Activity requests overlay access, notification access where applicable, and a fresh full-display MediaProjection consent. An optional Accessibility method requires explicit selection and Android service enablement on API30+; the screenshot flow does not read the accessibility hierarchy or inject gestures. A separate, explicit input-translation flow may inspect the focused ordinary editable node and apply text only after review and fresh identity/content checks; it excludes password fields and does not tap controls.
3. Foreground service owns the projection, registers its callback before creating a single VirtualDisplay, and does not restart without consent after process death. Accessibility sessions are bound to the enabled service and use a regular ongoing notification, without claiming a MediaProjection foreground session.
4. The capture boundary hides its own windows and waits for compositor fences. A sequence/timestamp check and a fresh ImageReader surface fallback prevent capturing a prior overlay buffer. Explicit pin/hide state is distinct from temporary capture hiding.
5. An optional normalized rectangle is cropped off the main thread. No screenshot file is created.
6. Frame fingerprints and a stability gate bound capture/OCR frequency. A conflated queue holds only the latest pending bitmap; discarded requests release their bitmaps.
7. OCR returns independent paragraphs with original-image geometry. Reading-order preparation separates columns, removes suitable wrap hyphens and preserves RTL order. Optional white-bubble grouping keeps manga balloons separate.
8. The translation boundary detects source language locally when requested, selects exactly one configured backend, applies language-specific corrections, splits only for provider limits, protects glossary terms and reuses bounded cached results.
9. Before showing the result, the service checks the request generation, settings and a new screen fingerprint. Rotation, region/settings/credential changes, stop and newer content invalidate prior work.

Projection, virtual display, image readers, surfaces, bitmaps, native OCR tasks, HTTP responses and coroutine jobs have explicit owners. Native OCR is allowed to finish reading before a cancelled caller can recycle its bitmap. The same VirtualDisplay resizes on rotation; its consent token is never reused to create a second display.

The initial selector waits for authoritative stored/displayed settings. An OCR-only selector owns a temporary normalized region that survives capture resize and rotation without overwriting the separately saved translation area. Its review pauses capture; closing it never turns a RECOGNIZE session into automatic translation.

Passage interaction combines touch and native-selection ownership. A long press acquires overlay focus; releasing the touch lease is posted after native TextView finishes ACTION_UP. Otherwise a synchronous automatic snapshot could hide the card before Android opens its selection toolbar. Native ActionMode then owns the pause until it ends. A passive dictionary tap does not acquire focus or alter the foreground application's system bars.

## Persistence and privacy

New files have new names and schemas. The old databases/preferences remain intact. Legacy import first produces a read-only preview, then adds supported records transactionally with source markers for repeat safety. Imported glossary language metadata is retained internally. Unsupported scopes and formats are reported rather than silently applied. History uses a separate Unicode-normalized search index and bounded Paging pages; full export streams from a frozen maximum ID outside the UI thread.

Secrets are separate from settings and profiles. AES-256-GCM uses Android Keystore, fresh IVs and service-specific authenticated data for translation, OCR and speech. Screenshots never enter history; history contains text only. Explicitly selected cloud OCR uploads image pixels; selected network translation uploads prepared text. The UI discloses these choices. Android cloud backup and device transfer exclude private application data; settings can be exported explicitly without secrets.

Both text UI and capture service use generation checks. Text UI cancels on editing, navigation and settings changes; capture additionally validates current pixels before publication. Network cancellation closes the actual OkHttp call and its body. The backend never falls back to an unselected online service.

An internal text-operation deadline ends the busy state with a localized retry instruction; cancellation of the owning screen/request remains silent. Both success and errors pass the existing settings/credential/rule generation checks, plus coroutine activity checks before and after the suspending revision guard. A timed-out or late obsolete request cannot replace a newer result.

Online explanation is available only for a native selection in the exact original OCR text. The service re-verifies source pixels before minting a one-use memory ticket. Opening the secure review performs no HTTP; explicit confirmation uses only the selected supported LLM and its exact vault identity. The bounded word/context/response live in memory for at most two minutes and never enter history, saved instance text or persistent files. Settings, key, rule, source invalidation or Stop cancel the real call and revoke the source lease. The capture pause outlives a terminal review state until its secure host disappears; recreation retains one owner without a gap.

## Images and native models

Each content URI is opened once into a bounded private temporary snapshot. Bounds, pixel decoding and EXIF all use those same bytes. Export rechecks the translated image fingerprint before drawing. Paragraphs that cannot fit legibly receive a numbered marker and complete footer text; export never silently cuts off a translation. White-bubble masks preserve pixels outside the balloon. This is deliberately limited to white bubbles, without neural restoration of arbitrary illustrated backgrounds.

The GGUF runtime builds an independently pinned official llama.cpp source archive with a verified SHA-256. It contains no legacy application wrapper or binary. A single mutex owns load/generation/unload; cancellation signals native work and drains it before disposing its session. CPU execution and JNI smoke tests have separate device evidence from model translation quality. An ARM64 APK running through the emulator's x86 native bridge is rejected before GGUF initialization because that bridge faults on a baseline half conversion; a native x86 test build is used for emulator GGUF checks. Physical ARM64 execution still needs its own verification.

The dictionary layer introduced in Room5 independently reads data-only schema1 SQLite packs, stages bounded batches until READY, and indexes exact words, forms and prefixes. Room6 retains its tables. It preserves rich senses and provenance, supports cancellation/startup cleanup, and exports through an independent bounded SQLite writer without a long Room read transaction. Flat TSV/JSON packs remain supported. Compatibility is with the documented data format; former application serializers, wrappers and binaries are not loaded.

Room6 adds persistent photo jobs and items. Each job owns bounded private source copies and separate bounded geometry/result files; large blobs do not enter a Room cursor. A single application-scoped runner serializes execution, while run tokens and current settings/credential/rule revisions guard each commit. Results and their history receipt commit together. Cold initialization repairs interrupted states and owned orphan files but never resumes translation automatically. Resume, Retry and creating a copy under current settings are explicit actions. Removing a job removes its own files and records, not the original user image or unrelated history.

Screen presentation consumes the accepted OCR document and its geometry. CARD uses a native selectable text surface; BLOCKS uses a passive bounded canvas with translated paragraphs over their original positions and a small control surface. Layout preparation runs away from the main thread. Presentation changes reuse accepted text only after the service verifies fresh pixels and the publication generation. A watch-only manual session can clear stale blocks without rerunning OCR or translation. Region fractions always refer to physical capture dimensions; the selector converts those dimensions to local drawing coordinates independently of system-bar insets.

Focused-field translation and Android PROCESS_TEXT use a separate review ViewModel, never saved instance text or implicit history. A focused request retains the exact supported native node identity and an expiring one-use ticket. Apply returns to the original window and repeats identity, original text, selection, field type and configuration checks before one ACTION_SET_TEXT. No background hierarchy inspection, generated taps, clipboard paste, Send or automatic retry is used. Password, web, Compose and unsupported specialized inputs are rejected. The PROCESS_TEXT path returns a writable caller's text only after explicit Apply; read-only callers have Copy and Share.

Explicit cloud adapters, CPU GGUF and white-bubble rendering have documented contracts and limits. GPU inference, arbitrary-color neural inpainting and other incomplete user scenarios remain visible in the feature matrix. A generic interface is not treated as proof of provider compatibility.
