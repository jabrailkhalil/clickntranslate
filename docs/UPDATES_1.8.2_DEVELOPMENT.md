# Settings and updates in 1.8.2 (unreleased)

This is local development work. No release or upload is part of this change.

## Settings

- **General settings:** startup, tray startup, hover tips, update checks, interface
  scale, cache/reset, settings export/import, diagnostics and hotkeys.
- **Translation and OCR:** OCR/translation engines, result-window modes and text
  size, automatic copy, histories, select-all before replacement, clipboard
  restoration, outside-click closing, and quick selection translation. The quick
  translation checkbox has a button/immediate selector on the same row.
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
  and enforces the existing TeamIdentifier when one is present. The complete
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

The package must have a matching SHA256 entry before any updater is launched.
Existing Mac manifests with a `releases/` filename prefix remain readable; new
Mac builds write basename-only entries. Build defaults, Windows manifests and
Linux AppStream metadata follow the existing development version, 1.8.2.

## Validation boundaries

Automated tests cover six UI languages, both themes, scales 80–150%, visible
controls and selector text fitting, persistence, guide routing, one-page update
states, checksum failures, archive traversal/symlinks and actual shell rollback
with user-data preservation. Windows tests invoke the compiled helper's quiet
CLI against disposable installations, including damaged files and a crashing
GUI. POSIX transaction tests on Windows use the bundled MSYS shell/coreutils;
they do not establish native Linux or macOS GUI compatibility.

Native Mac verification is pending connection of the user's Mac. Native Linux
bundle replacement and real Inno installation need their respective runners.
The final local regression totals are stored in `settings-update-validation.json`.

Implementation references: [PyInstaller subprocess environment guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application),
[Apple code-signature verification](https://developer.apple.com/library/archive/technotes/tn2206/).
