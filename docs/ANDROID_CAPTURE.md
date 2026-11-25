# Android screen capture

## Sources and permission ownership

`CaptureService` owns one `FrameSource`, its overlays and session coroutine scope. A source returns
caller-owned software bitmaps through `captureAfter(marker, hiddenAtNanos)`; the caller releases them.
The two sources share the same crop, OCR/translation pipeline, request queue and result publication.

| Source | Availability | Explicit setup and lifetime |
| --- | --- | --- |
| `ProjectionFrames` | Android 8.0 / API 26+; default | Android overlay permission, fresh MediaProjection consent for each session, a `mediaProjection` foreground service and ongoing notification. The callback is registered before creating one VirtualDisplay. |
| `AccessibilityFrames` | Android 11 / API 30+; optional | Select Accessibility capture, read its disclosure and enable the service in Android settings, then explicitly start a session. It uses the official `AccessibilityService.takeScreenshot` API. The enabled service binds the capture controller; it does not claim a MediaProjection foreground grant. |

Both methods require overlay access. Android 13+ notification permission is requested for notification
controls; its grant does not authorize screenshots. Accessibility enablement alone takes no screenshots.
This service does not retrieve app view hierarchies, inject gestures or operate other apps. On API 26–29,
the UI uses MediaProjection instead of the unsupported Accessibility method.

## Freshness, cancellation and rotation

Before reading pixels, the controller temporarily hides its own windows and waits for UI frames.
MediaProjection checks image sequence/timestamps and can replace its ImageReader surface to obtain a
fresh static frame, retaining the same VirtualDisplay. Accessibility checks the screenshot timestamp
and spaces native screenshot calls by at least 500 ms, with backoff and shutdown after repeated failures.
A snapshot timeout produces an error instead of publishing an old buffer.

Automatic capture polls no faster than every 800 ms. A small luminance/edge fingerprint detects changes;
the stability gate waits for content to settle and skips previously submitted stable content. This is
perceptual comparison, not a pixel-perfect guarantee for every tiny edit or animation. The conflated
queue retains at most one pending bitmap. Superseded requests are cancelled and discarded images are
recycled. Before publication, generation, semantic settings and a fresh screen fingerprint are checked.

Language/provider/OCR/model/region changes, credential invalidation, newer content, rotation and stop
invalidate old requests. Appearance and pin changes do not unnecessarily restart OCR. HTTP cancellation
cancels the actual OkHttp call. Native OCR tasks finish reading their bitmap before cancellation releases
it; their cancelled result cannot be published.

Rotation resizes the existing VirtualDisplay and ImageReader rather than reusing consent to create a
second display. Saved regions use normalized coordinates in the current display orientation. Rotation
clears the previous result. Reader replacement closes the preceding reader even if resize fails; session
closure rejects queued resize/error callbacks before asynchronously disposing worker-owned resources.

## Controls and stop policy

Tap the movable floating button to translate; hold it for area/automatic/pin/hide/stop actions. The area
editor supports moving/resizing and saves the normalized rectangle. Notification **Show** restores a
hidden button in an active session; **Stop** releases the session. The Quick Settings tile opens the
explicit start flow or stops a running session. An old Show action cannot restore a stopped grant.

Button and result pinning suspend their independent inactivity timers; zero disables a timer. Unpinning
starts a full new interval. Pinning keeps an element visible and does not lock the button's position.
Temporary screenshot hiding preserves this intended visibility. Changed content clears an obsolete
automatic result even when pinned. A selected custom button image is imported through the system
picker into a private normalized 512 px PNG. Profiles/settings contain an opaque filename, not the source
URI or image bytes; another device must select its image again. Missing art falls back to the companion.

A service-lifetime, non-exported receiver handles the protected system `ACTION_SCREEN_OFF` broadcast.
Going non-interactive explicitly stops active capture on **all API 26+ versions**, including Accessibility.
Unlocking does not resume capture. Start a new session; MediaProjection requests new consent. Newer
Android's own projection-stop callback is an idempotent second stop path. Stop invalidates results,
cancels work and queued images, removes overlays/timers/notification, closes reader/display/projection
resources and terminates the capture worker. The service uses `START_NOT_STICKY`.

## Protected content and privacy

Android may hide or reject `FLAG_SECURE`/DRM content. Black/empty frames or screenshot errors are
reported; the app does not bypass protected windows. Device lock, permission revocation, another
projection or process termination can end a session. Reboot/process-death recovery never silently
restores a MediaProjection grant.

Defaults are local OCR, offline translation and automatic mode off. Local OCR never silently falls back
to cloud OCR. Only explicitly selected Google Vision/custom HTTP OCR uploads image pixels; a selected
network translator receives prepared text. The UI discloses both choices. Offline models may need a
download, which is separate from sending screen content. No screen bitmap is written to disk or stored
in history; optional history contains text. Secrets remain separate from settings/profile exports.

Gallery/Share photographs have a different lifecycle: `ImageInput` opens their URI once into a necessary
private encoded temporary snapshot capped at 64 MiB. Bounds, decoded pixels and EXIF use those same
bytes, with a 2400 px decoded-edge limit. Completion/error/cooperative cancellation removes the snapshot;
the next operation sweeps only this component's orphan files and preserves concurrent active files.
A killed process can leave a temp until that sweep. A provider stuck indefinitely in a blocking open/read
cannot be interrupted by a between-chunk cancellation check. These photo temps are not screen captures.

## Reproducing device checks

### Next-iteration overlay actions and application rules

The staged overlay uses a platform Dialog/DecorView so Android's native TextView selection ActionMode
can offer Listen, Dictionary and Stop speech. Only the selected logical UTF16 range is consumed;
missing/empty ranges never select the whole card, and surrogate boundaries are preserved. Dictionary
queries use the translated card's target language as the pack source, then each installed eligible
pack's exact declared language pair. There is no other-language/global dictionary fallback. Lookup is
limited to 256 characters and bounded result previews. Speech uses the configured scoped Speech
facade, waits for native initialization and displays real availability/audio-focus failures.

Quick profile selection uses the displayed row's Room id and rechecks the authoritative profile row.
Basic restores the saved basic configuration through the same store helper. Processing is gated until
the latest DataStore/service snapshot settles; a cancelled older apply cannot reopen the gate. A
capture-method change stops the session and asks for a fresh Start. No profile grants OS permissions.

Requests and selected actions carry direct credential and rule revision stamps, so a completed worker
cannot publish just because its invalidation collector has not run yet. Context/selection changes,
navigation, profile/language/key/rule edits, screen-off and session stop cancel speech/lookups. Controls
and service messages cover English, Russian, German, French, Spanish and Simplified Chinese; broader
typed translation/OCR error localization is a separate task.

Application-scoped glossary/correction rules optionally use explicit Android Usage Access. Without
enabled app-scoped rules there is no app monitor or UsageStats query. With them, a 750 ms session
monitor and forced reads before/after capture and before publication check package evidence independently
of pixels; identical screenshots in different apps invalidate the old request. Denial, lock, errors,
over-limit queries or ambiguous resumed packages produce null and cannot activate an app-specific rule.
The helper scans at most 10000 events, replays a bounded 5-second overlap for delayed delivery and never
persists a usage history or sends package evidence to translation providers.

This is best-effort UsageEvents evidence, not reliable per-window attribution or a security boundary.
OS event latency can delay detection, and a paused-but-visible split-screen app on older Android may
not be distinguishable from these events. Multiple simultaneously resumed packages fail closed where
that evidence is available. Unknown context uses global rules only, never the previous known package.

Selected actions and quick profiles have a separate current-iteration API 36 runtime check recorded
below. Real application-context changes and Usage Access revocation are covered by the later QA3
API 26 suite; the older baseline must not be used as their pass result. Additional commands:

```powershell
adb -s emulator-5584 shell am instrument -w -r -e class dev.clickn.translate.next.capture.OverlayActionsIntegrationTest dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5584 shell am instrument -w -r -e class dev.clickn.translate.next.capture.OverlayWindowLifetimeIntegrationTest dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
```

Commands assume `adb` is on PATH, an unlocked test device without an unattended PIN prompt, and the
debug application/test APKs are installed. Replace `emulator-5580` with the intended serial. Debug uses
`dev.clickn.translate.rewrite`; production remains `dev.clickn.translate`. Debug fixtures are absent from
the release build. Default build ABI is ARM64; a native x86 emulator build may use `-PtestAbi=x86_64` for
debug testing only. An emulator native bridge is not physical ARM64 validation.

```powershell
.\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest
adb -s emulator-5580 install -r app/build/outputs/apk/debug/app-debug.apk
adb -s emulator-5580 install -r -t app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb -s emulator-5580 shell am instrument -w -r -e package dev.clickn.translate.next.capture dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5580 shell am instrument -w -r -e class dev.clickn.translate.next.capture.ProjectionRevocationIntegrationTest dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5580 shell am instrument -w -r -e class dev.clickn.translate.next.capture.SleepCaptureIntegrationTest dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5580 shell am instrument -w -r -e class dev.clickn.translate.next.capture.AccessibilityCaptureIntegrationTest dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5580 shell am instrument -w -r -e class dev.clickn.translate.next.media.ImageInputIntegrationTest dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
```

`ProjectionRevocationIntegrationTest` obtains a second real full-display Android consent and public-API
projection, causing Android to revoke the original grant. On older Android it closes the initial card
for unobscured consent, then recreates it through actual OCR before activating the new grant; both
real overlay windows must exist at the moment of revocation. `SleepCaptureIntegrationTest` uses `UiDevice.sleep()`,
observes the actual protected SCREEN_OFF broadcast, then wakes/cleans up the device. Both inspect real
WindowManager windows, notification and reader-thread disposal and reject restoration via an old Show.
Run sleep on API 26 as well as newer Android to exercise the app policy independently of QPR behavior.
Accessibility tests use a narrowly adopted test-only WRITE_SECURE_SETTINGS identity and restore prior
settings; production cannot enable its own service. ImageInput tests use real mutable/oversized provider
streams, EXIF mirrors, cancellation and concurrent snapshot cleanup. On failure, revocation/sleep tests
keep bounded diagnostics in the debug app's `externalFilesDir/capture-diagnostics`: screenshot, hierarchy,
state/stage trace, activity/window dumps and main-thread stack. Fixed case/API filenames overwrite the
previous failure's artifacts; production does not capture these diagnostic files.

The soak is deliberately skipped in a normal suite unless enabled explicitly. It supports 30 seconds
through 1 hour, repeatedly changes actual fixture pixels, verifies fresh OCR and unchanged-frame
deduplication, checks the single owned worker and verifies its removal after stop:

```powershell
adb -s emulator-5580 shell am instrument -w -r -e class dev.clickn.translate.next.capture.AutomaticCaptureSoakTest -e runCaptureSoak true -e captureSoakMs 600000 dev.clickn.translate.rewrite.test/androidx.test.runner.AndroidJUnitRunner
adb -s emulator-5580 logcat -d -s CaptureSoak:I
```

Read the runner's assertions and `OK (...)`/failure report; adb process exit alone is not test evidence.

## Recorded evidence and remaining checks

Historical API 35 emulator run, ARM64 APK through the ARM native bridge: the requested 10-minute soak
**passed**, instrumentation time **606.978 seconds**, **116 cycles**, maximum observed PSS
**335282 KB**. Local execution log: `.tmp/wave2-android35-soak-10min.txt`; cycle/PSS data came from
`CaptureSoak` logcat. This snapshot predates the new stop/resource fixes and SDK 36 changes and is
**not final validation of the current build**. Maximum PSS alone does not establish absence of leaks.

The first SDK 36 x86 test runs found revocation-test setup failures on API 26 and 36: an existing overlay
occluded the old permission dialog, and the newer default flow opened a single-app selector. The fixture
now requests full-display consent and restores actual OCR overlays before activation. The sleep check
passed on API 26 but exposed a transient stopped/visible status race on API 36; teardown status was
corrected. Initial logs: `.tmp/wave2-sdk36-android26.txt`, `.tmp/wave2-sdk36-android36.txt`.

The rebuilt x86 debug APK subsequently **passed both targeted revocation and sleep tests on API 26**:
`OK (2 tests)`, **14.734 seconds**, `.tmp/wave2-capture26-fixed.txt`. The trace records actual consent,
successful public `getMediaProjection` and grant disposal; the assertions checked real overlay/window,
notification and reader-worker cleanup. MediaProjection was null after cleanup.

The later baseline at source commit `5a6c3555c8441d2ad72c51b35b5ba359c7a3593d` passed its full API 26
and API 36 runs: each reported `OK (65 tests)`, 63 pass / 2 explicit skips. See
[API 26 log](qa/wave2/android26-instrumentation.txt), [API 36 log](qa/wave2/android36-instrumentation.txt)
and [validation ledger](qa/wave2/validation.json). This includes the corrected stop/sleep scenarios, but
predates the next-iteration scoped credentials, selected actions, quick profiles and application-rule
changes described above. Their current-build checks remain separate.

The next-iteration x86 debug snapshot `.tmp/wave3-x86-overlay-fix/` passed the API 36 targeted suite:
**`OK (7 tests)`, 73.413 seconds**, `.tmp/wave3-overlay-capture36-fixed.txt`. This covered actual-screen
OCR, selected-text dictionary lookup using only the card's source-eligible declared language pairs,
speech preparation/error reporting for the exact selection, authoritative quick profile/basic restoration,
backend-change stop, pre-attachment overlay disposal, pin/timer/notification controls, real device sleep
and real OS projection revocation. The suite ran in one instrumentation process, so later cleanup
assertions also checked that earlier profile/selection actions had not leaked overlay windows. The
first attempt exposed a WindowManager root removed before View attachment and asynchronous smart
selection expansion; the rebuilt snapshot removes registered roots regardless of attachment and keeps
native selection handles without smart expansion. Listen checks do not establish audible voice quality;
neither this targeted run nor the earlier baseline establishes physical ARM64 behavior.

The later QA3 x86 full suite passed on API 26: **`OK (84 tests)`, 135.875 seconds**, 82 passes and two
explicit skips, `.tmp/wave3-android26-candidate.txt`. However, its new automatic soak **failed at cycle 0**:
the focused result Dialog restored the status bar of a fullscreen foreground app. Its next OCR result
included `S 10:36` above the unchanged fixture text. This was a real frame change caused by our own
window focus; the full-suite result must not be presented as a successful QA3 long run.

QA4 makes idle cards nonfocusable, acquires focus only for a touch inside selectable text, releases it
before resuming automatic capture, and accepts a fresh frame only after overlay hiding has settled.
The API 26 native selected-action/profile checks passed again: **2 tests, 30.663 seconds**,
`.tmp/wave4-overlay-actions26-candidate1.txt`. The following one-minute full-frame automatic check passed:
**68.063 seconds, 11 cycles, maximum observed PSS 147841 KB**, including zero owned worker threads and
zero overlay windows after stop. Logs: `.tmp/wave4-android26-soak60-candidate1.txt` and
`.tmp/wave4-android26-soak60-metrics.txt`. A later API26 candidate4 completed604.452s/103cycles
with maximum PSS168763KiB, and API36 candidate6 completed605.379s/101cycles with maximum
PSS275183KiB after the broader OCR/model suites. Both released owned windows and their frame worker.
These intermediate measurements predate the final history/native-window fixes and do not substitute
for the current-build checks recorded in the [QA journal](REWRITE_STATUS.ru.md).

## Accepted automatic results and native selection teardown

Pixel changes still trigger stability checks and fresh OCR. Identical consecutive accepted automatic
documents now share one history row even when non-text background pixels change. The service keeps
one length-delimited SHA256 key, input settings, credential/rule revisions and application context;
it does not retain previous image pixels. Manual requests, A→B→A visits and changed input identities
remain separate. The accepted key advances only after freshness guards and actual window publication;
cancelled work, failed windows and rolled-back owned history rows cannot advance it.

The new real-pixel regression failed before this policy with two byte-identical OCR/translation rows,
then passed on both API26 and API36. The initial full-suite duplicate is preserved separately; its
exact transient-frame cause was not inferred from the controlled background test.

A later API26 run exposed a server-side `WindowContainer.removeIfPossible` exception while native
selection child windows and their parent Dialog were removed together. The parent remained focused
after its input channel closed, causing a subsequent input timeout. Teardown now detaches overlay
ownership before callbacks, guards closed windows against re-show, releases focus/touch immediately,
and finishes native selection before dismissing its parent. For API26/27 windows which used native
selection, the hidden parent remains owned by a bounded main-handler cleanup through the native
toolbar's animation and one frame, with a no-vsync fallback. No UI thread is slept or blocked.

Primary platform references for this workaround:
[Android8 WindowContainer](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-8.0.0_r1/services/core/java/com/android/server/wm/WindowContainer.java),
[Android8 FloatingToolbar](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-8.0.0_r1/core/java/com/android/internal/widget/FloatingToolbar.java).
Real native-handle tests cover repeated close/focus/window cleanup, prevention of re-show after close,
and cleanup while the device is asleep. Final run identities and preserved failures belong in the QA journal.

Further separate checks include physical
ARM64 power/thermal behavior, protected windows, process death/reboot, simultaneous rotation/revocation,
and stop during a live pending cloud request.

Official API references: [MediaProjection lifecycle](https://developer.android.com/media/grow/media-projection),
[Accessibility screenshots](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#takeScreenshot(int,java.util.concurrent.Executor,android.accessibilityservice.AccessibilityService.TakeScreenshotCallback)),
[SCREEN_OFF](https://developer.android.com/reference/android/content/Intent#ACTION_SCREEN_OFF),
[receiver lifetime and export flags](https://developer.android.com/develop/background-work/background-tasks/broadcasts).
