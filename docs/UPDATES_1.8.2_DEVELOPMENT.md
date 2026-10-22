# Settings and updates in 1.8.2

This document describes the desktop update implementation and its validation
boundaries. Release files are listed in the [1.8.2 download table](RELEASE_1.8.2.md).

## Settings

- **General settings:** startup, tray startup, hover tips, update checks, interface
  scale, result-text size/preview, cache/reset, settings export/import,
  diagnostics and hotkeys.
- **Translation and OCR:** OCR/translation engines, result-window modes,
  automatic copy, histories, select-all before replacement, clipboard
  restoration and outside-click closing. Selection triggers (hotkey, nearby
  button, immediate translation) belong to the existing selection mode's
  language settings, rather than separate duplicate settings checkboxes.
- **OCR options:** an expandable section on the translation page contains
  keep-visible, freeze-screen, dimming and copy notifications.

The translation page has its own scroll viewport for expanded OCR options or
constrained text layouts. It cannot extend underneath the program action panel.
Guide links open the corresponding category and reveal collapsed OCR controls.

## Update flow

Check, install/later consent, download, verification, cancellation and errors use
one embedded settings page. Startup update offers use that page too, retaining
the skip-version action. A running update keeps its page alive through theme
changes and attempted settings rebuilds. Closing requests cancellation before
handoff; once replacement starts, the app finishes its restart sequence.

- Windows retains the verified helper and checksum/manifest/startup checks. The
  helper runs with `--quiet true`; Inno updates use `/VERYSILENT`. Elevation, when
  required, remains an OS prompt. Failure is reported inside the restored app.
- macOS selects the architecture-specific ZIP, validates archive paths and the
  symlink graph, extracts with `ditto`, checks bundle ID/version and signature,
  and enforces the installed application's designated signing requirement.
  This pins the previous certificate even when TeamIdentifier is absent. The complete
  `.app` is replaced by rename, rather than modifying its signed files in place.
- Linux selects the architecture-specific AppImage or portable tarball. A tar
  installation must have the build-created `.cnt-portable-install` identity;
  system/package-manager installations are not replaced by this updater. Every
  non-program top-level item is retained, including hidden and personal files.

POSIX preparation happens before the original app closes, on the target's
filesystem. A detached system-shell runner keeps a backup, waits for the original
process, replaces the target, starts the new GUI, checks its exact version
acknowledgment and waits five seconds for stability. Failure restores the old
files and reopens the previous version. Paths are passed as separate, quoted
arguments. The helper environment clears the previous frozen/AppImage runtime.
An update restart skips blocking Welcome and startup introductions without
changing the user's preference for ordinary starts. The POSIX download is
removed after the detached runner has received its independent staged copy.

No compatible package, a broken download or a server error stays inside the
update page, with retry/back actions. These states do not open a GitHub page.
GitHub Releases remains the distribution backend; the application retrieves
the release metadata and binary files itself. No manual browser download is
part of the supported in-app update flow.

The package must have a matching SHA256 entry before any updater is launched.
Existing Mac manifests with a `releases/` filename prefix remain readable; new
Mac builds write basename-only entries. Build defaults, Windows manifests and
Linux AppStream metadata follow the existing development version, 1.8.2.

## Validation boundaries

Automated tests cover eight UI languages, both themes, scales 80–150%, visible
controls and selector text fitting, persistence, guide routing, one-page update
states, checksum failures, archive traversal/symlinks and actual shell rollback
with user-data preservation. Windows tests invoke the compiled helper's quiet
CLI against disposable installations, including damaged files and a crashing
GUI. POSIX transaction tests on Windows use the bundled MSYS shell/coreutils;
they do not establish native Linux or macOS GUI compatibility.

Native update integration now runs with `tools/qa_posix_update.py`: actual
Settings buttons in a source Qt controller, an HTTP release fixture, real
downloads/checksums, the production detached runner and a real frozen GUI.
Only the source controller's frozen-install discovery/current version is
simulated; readiness comes from the actual launched application. Mac uses an
isolated 1.8.1 app copy and the signed 1.8.2 ZIP. Linux fixtures use existing
1.8.1 AppImages and an explicitly marked copy of the old portable runtime.
This validates update mechanics, not a future published release feed or the
existence of the new updater in an older released GUI.

Success, cancellation, bad checksum, unavailable asset, server failure and
rollback after a GUI crash passed on native Mac and Linux AppImage. Portable
Linux directory replacement and rollback also passed. Test profiles, models,
hidden files and personal-file markers survived. Linux AppImage rollback
kills the actual GUI PID (rather than just its outer runtime) and checks a
different recovered GUI PID. Mac production signature verification accepts
the previous certificate and rejects an independently valid ad-hoc signature.

Early private 1.8.2 archives predated the Welcome and theme-button fixes and
were replaced before publication. Runtime packages are built from commit
`4de4e107797f050cfc5e1d6725252742ab362993`; subsequent documentation commits
do not change their runtime source. The source-controller boundary above
remains explicit even after native package checks.

The signed Mac control build and Linux portable control build passed an
additional 1.8.1 -> 1.8.2 transaction with `--welcome-enabled`: the real new GUI acknowledged readiness and remained
responsive, while `show_update_info=true` stayed unchanged. This specifically
reproduces the preference that blocked readiness in the earlier binary.

Implementation references: [PyInstaller subprocess environment guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application),
[Apple code-signature verification](https://developer.apple.com/library/archive/technotes/tn2206/).
