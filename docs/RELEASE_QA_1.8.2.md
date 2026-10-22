# Click’n’Translate 1.8.2 validation

Checked on 22 October 2026. Desktop runtime packages use source commit
`4de4e107797f050cfc5e1d6725252742ab362993`. Later release-documentation commits
do not change their runtime source. Android uses the separately prepared
artifact recorded in [release-identity.json](../tools/packaging/android/release-identity.json).

## Complete desktop source suites

| Native environment | Passed | Skipped | Additional passing subtests | User data |
| --- | ---: | ---: | ---: | --- |
| Windows x64 | 2206 | 77 | 1279 | Unchanged |
| macOS ARM64 | 2139 | 144 | 1276 | Unchanged |
| Linux x86_64 | 2170 | 113 | 1285 | Unchanged |

Skipped cases require a different operating system or build tools absent from
that test environment. Separate signing, installer and native-package checks
cover the release files. Passing a source test alone is not proof that a frozen
GUI button works.

## Theme-button regression

The performance decorator accepted arbitrary arguments, so Qt forwarded
`clicked(bool)` to a method that only accepted `self`. Direct method calls in
earlier tests did not expose the error. The handler now declares its zero-argument
Qt slot explicitly. The regression test failed before the fix and passed after it.

Tests drive the actual signal and visible scaled button at 80, 100, 137 and
200 percent, in both home and settings, checking that the theme changes, the
painted background follows it, and child settings receive the new palette.
The Mac frozen smoke now requires a changed theme after each click, rather than
merely checking the existing palette. The final signed Windows EXE was clicked
in both directions; Mac ARM and Intel frozen checks exercise eight theme clicks
and sixteen painted frames each.

## Native packages and updates

- Windows: native launch, an actual online text translation, result expansion,
  language menus, API/package navigation, mascot selection and both themes.
  Eight clean-runner transitions cover 1.6.0/1.6.1 ZIP and 1.7.0/1.8.0/1.8.1
  ZIP and installer baselines. Checks bind to the final candidate file hashes,
  verify every program-manifest entry, preserve user-data/model markers and
  require the actual frozen GUI to acknowledge readiness and start again.
- Mac ARM: LaunchServices/Cocoa, settings, native Vision OCR, Carbon event
  delivery, RapidOCR, Argos and Keychain. The installed app retained its signing
  requirement; its Screen Recording and Accessibility access remained available,
  and real screen capture returned a nonempty image. A fresh 1.8.1 → 1.8.2 ZIP
  transaction passed with Welcome enabled and preferences/models preserved.
- Mac Intel: signed native GitHub build, the same frozen GUI/helper smoke, and
  an additional Rosetta run on the available ARM Mac.
- Linux: native X11 package checks in an isolated virtual display, RapidOCR and
  Argos workers, and AppImage replacement/readiness and crash rollback. The
  final package uses the same Python 3.12 environment as its source tests.

POSIX update integration uses a source Settings controller with only its
installation discovery and current version overridden. HTTP download, checksum,
production runner, replacement, restart, new frozen GUI and readiness are real.
It does not imply that a released 1.8.1 Mac/Linux GUI already contains this
updater. First upgrading those versions to 1.8.2 remains a manual installation.

The unchanged updater code also passed cancellation, checksum rejection,
unavailable-asset, server-error and rollback scenarios during the native audit.
See [update scope](UPDATES_1.8.2_DEVELOPMENT.md).

## Data, engines and API connections

Coverage includes eight desktop locales and hints, guide routing, settings
categories and control bounds, separate scale/result-text settings, documents,
selection/replacement options, local histories, settings import/export and
diagnostic redaction. API transport, credential isolation, rejected redirects,
error/quota/timeout responses and response parsing use controlled HTTP fixtures.
No live paid-provider account is claimed as tested. A live Google translation
was checked in the frozen Windows GUI.

## Signatures and Android

Windows executables, helpers, updater and installer retain the previous
jabrailkhalil certificate and timestamp. Independent Authenticode verification
checks their cryptography and timestamp chain; a modified control is rejected.
Mac apps, native components and DMGs use the previous permanent self-signed
identity. All nine application packages have detached OpenPGP signatures and
SHA-256 entries in the verification archive. Public identities are documented
[here](SIGNING_IDENTITIES.md); private keys are not committed.

The Android preparation report records 1660 passing tests, 21 UI captures,
successful assembleRelease/lintRelease, signature/CRC/manifest/native-library
checks and no debug flag. This release reuses that APK unchanged and repeats
its signature and artifact-hash verification. The original Android signing
identity is recorded for future updates.

## Practical limits

No physical Android phone was tested in this release preparation. X11 virtual
display tests do not establish compatibility with every Wayland compositor.
Windows/Mac certificates are self-signed; the Mac app is not Apple-notarized.
Online providers have their own availability, accounts, prices and limits.

README media consists of new step sequences captured from the running Windows
1.8.2 GUI with synthetic demonstration text. The translation is a real online
result. Screenshots are not generated mockups, and no personal documents or
keys appear in the recordings.
