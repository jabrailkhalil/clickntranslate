# Windows integration of the shared Mac work

2026-09-11. Source version: 1.7.1; this work does not publish a release.

Integrated `origin/main` at `97d3e74` into `codex/windows-mac-sync`. This is a
complete fast-forward from `c55a899`, preserving the Mac work and dependencies:
inline source/result fields, progressive translation, editable/collapsible
result windows, compact themed hints and OCR controls, dynamic region editing
and scrolling, provider/package changes and platform-specific startup. Native
Mac facilities remain guarded by the platform. The older
`codex/shared-hover-tooltips` implementation is superseded by the compact hint
implementation already in `main`.

## Full-screen translation report

The user reported words collected at the left after a Windows update; the
installed version, screenshot and diagnostic report were unavailable. We
cannot establish which installation or failure caused that specific report.
The public GitHub release API on September 11 still listed **v1.7.0, published
September 1**, as latest. The prepared 1.7.1 source/Mac artifacts had not been
delivered through the updater.

The audit found and corrected two independent positioning defects:

- Windows OCR returns rectangles in deskewed image coordinates when
  `OcrResult.TextAngle` is nonzero. The old worker ignored that angle. A native
  three-column fixture reproduced offsets even on ordinary horizontal text;
  mapping each word rectangle around the capture center restores its position.
  See [Microsoft's coordinate contract](https://learn.microsoft.com/uwp/api/windows.media.ocr.ocrresult.textangle).
- A rectangle entirely outside the viewport was forced to `(8, 8)`, stacking
  unrelated translations at the top left. Such rectangles now paint nothing;
  nonfinite/invalid OCR boxes are excluded before grouping.

Full-screen translation also captures the chosen translator for all its batches
and propagates cancellation. A stale operation cannot keep issuing requests
after the overlay is closed or its language pair changes.

Native probe: `.venv/Scripts/python.exe tools/qa_windows_fullscreen.py` on
Windows with English Windows OCR installed. It creates a fixture, runs the
real positioned OCR worker at 100/125/150/200% capture scale and checks all three
columns. Translation responses are deterministic test strings. It does not
capture the desktop or contact providers. Generated images and the JSON report
are in `.tmp/windows-mac-qa`.

## Update confirmation

Previously the public launcher wrote its own version to `--update-ack` as soon
as it spawned a process. That could mark an old or uninitialized application
as an updated one. The launcher now only forwards arguments. The application
publishes its runtime version atomically after its GUI event loop starts.
The updater checks versions of the launcher, application, OCR/Argos workers and
the packaged updater before launch.

Runtime tests compile the actual Windows launcher/updater, launch ready and
unready test children, and reject an old inner executable under a new launcher.
Existing rollback and startup timeout behavior is retained.

### Every shipped module is verified

`release_manifest.py` writes `program-files.sha256` after staging and signing.
It inventories every immutable program file: workers, Python archives, DLLs,
Qt plugins, icons and other bundled resources. The Windows updater verifies
the manifest before copying a ZIP and after installation (ZIP or Inno Setup),
before discarding the backup. Missing, changed or unlisted program files fail
verification. A new launcher cannot conceal an old inner executable or worker.

The running application also verifies this inventory before acknowledging an
update. This is needed for upgrades launched by a pre-1.7.1 update helper,
which cannot know about the new inventory format. Only the application writes
the acknowledgement, so the legacy helper cannot receive premature success
from the new launcher.

The entire previous program is moved aside, so obsolete modules disappear.
`data`, downloaded `ocr`/`translators` packages and installer metadata are kept.
ZIP extraction cannot overwrite these user folders even if the archive contains
default data. If creating the backup fails halfway, already moved items are
restored without deleting the old files that have not moved yet.

The real compiled update helper is exercised through both ZIP and Inno Setup
paths in disposable directories with a temporary installer AppId. Tests include
changed/missing modules, complete rollback, failure midway through backup,
an active old OCR process, and preservation of settings/history/models. No
production installation is used by these tests.

## Integration regressions

The first full test run detected loss of a completed document chunk when
cancellation arrived with the response. Completed chunks are retained again;
further requests and partial UI callbacks still honor cancellation. Two old
tests were updated for the new source/result captions and progress callback.

## Validation

- Windows full suite: 1,189 passed, 42 skipped, 895 subtests passed.
- After the final Windows OCR angle correction: 91 OCR/dynamic-mode tests passed.
- Native Windows OCR fixture passed at all four capture scales; reviewed the
  rendered replacement positions and the main UI in both themes.
- Linux full suite: 1,131 passed, 67 skipped, 901 subtests passed. After adding
  the full update inventory: 139 focused checks passed, 21 Windows checks skipped.
- The complete update inventory, compiled updater/installer checks and existing
  update/signing tests passed (97 checks), followed by the full Windows run.
- The staged Windows package contains 4,004 inventoried program files. The real
  frozen launcher/application passed an isolated GUI-startup smoke check and
  published version 1.7.1 only after verifying the entire inventory.
- Startup diagnostics now distinguish missing files, explicit Windows antivirus
  errors, access denial and other failures. Reports include module versions,
  modification times and update-marker/backup metadata, without reading user
  settings. The launcher/report checks passed (10 tests). The updater no longer
  claims successful rollback when recovery itself fails.
- After the startup-diagnostics/recovery-message changes, the final inventory,
  compiled ZIP/Inno updater and signing suite passed again (98 tests).

Native Mac runtime testing must be repeated there for shared-code changes;
Windows/WSL checks do not establish Cocoa or Retina behavior on a Mac.
