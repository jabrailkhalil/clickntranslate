# Native Mac update — 7 September 2026

This folder records the integration of the editable translation window and
Cocoa popup fixes into Click’n’Translate 1.7.1 arm64. See
[the main report](../../../MACOS_QA.md) for scope and remaining acceptance.

- `validation.json`: final suite counts, architecture and artifact SHA-256.
- `installed-smoke.json`: 310 screenshots rendered by the installed app via
  LaunchServices; this folder contains selected images, the local QA archive
  contains the complete matrix. Screenshot DPR is 2.
- `installed-smoke-*.png`: final installed GUI backing-store captures.
- `light-*-screen-unlocked.png`: actual screen crops after the native
  transparency fix, before the final lifetime change. These show why checking
  only a Qt pixmap was insufficient. They are earlier source fixtures.
- `final-screen-*.png` and `popup-native-capture.json`: eight final screen
  captures of isolated Cocoa fixtures after unlock, with DPR 2 and transparent
  native window backgrounds. Both themes were visually reviewed.
- `screen-capture-limitation.json`: the earlier locked-screen capture was not
  counted; the retry after unlock passed.
- `workspace-live-*`: real source-window Google requests and a controlled
  LibreTranslate HTTP 503. Qt-local input, no physical keyboard or external-app
  clipboard test. These fixtures use isolated configuration and no auto-copy.
- `installed-workers-qa.json`: real frozen EasyOCR and offline Argos. The raw
  Argos helper returns null for a missing pair; the GUI translation layer raises
  an error instead of selecting another provider.

Native tests are distinct from manual OS acceptance. The UI-control service
could not start. Screen Recording and Accessibility remain ungranted for the
installed app; Developer ID/notarization are not configured.
