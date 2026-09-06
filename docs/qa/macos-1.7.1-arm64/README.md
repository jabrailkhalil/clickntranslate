# Native Mac evidence, 2026-09-06

See [MACOS_QA.md](../../MACOS_QA.md) for scope, findings, commands and limitations.
These files record the actual Apple M1 / macOS 14.3 run. Unit tests with platform
mocks are distinguished from native Cocoa, Vision, Carbon, screen capture and
real provider/package requests in that report.

- `installed-smoke.json`: final installed application, launched with LaunchServices;
  300 screenshots, with seven representative images/fixtures committed here.
  The remaining images and the original logs/QA scripts are in the local QA ZIP
  linked from the report. Relative screenshot filenames refer to `build/macos`.
- `test-results.txt`: tails of both full pytest runs and the focused Cocoa checks
  after the final package-page theme correction.
- `runtime-qa.json`, `easyocr-qa-summary.json`, `installed-workers-qa.json`:
  actual provider calls, package lifecycle and frozen helper results. Timing
  reflects this run only. A helper's missing Argos pair returns `null`; the GUI
  translation layer raises the explicit error recorded in `provider-errors-qa.json`.
- `capture-qa.json`: QScreen capture of our own fixture. Its `target_window=0`
  entry was not a passing tracking check; tracking was tested independently in
  `window-tracking-qa.json` with the fixture's actual Quartz window number.
- `installation-qa.json`, `compatibility.json`, `artifacts.json`: DMG installation,
  ad-hoc signature, actual Mach-O minimum OS versions, file sizes and SHA-256.
- `autostart-qa.json`: actual temporary LaunchAgent installation/removal, with
  unrelated agents preserved. No logout/login was performed.
- `lifecycle-qa.json`: installed instance accepted IPC; duplicate `--autostart`
  exited without replacing the existing process. The interactive replacement
  dialog was not exercised.

Screen Recording and Accessibility were **false** for the installed application
through LaunchServices. They were **true** for the source capture process. The
user must still grant the installed application's permissions and complete the
manual acceptance checks. No permission database or system protection was changed.

Only synthetic text/images were sent to translation/OCR providers. User settings,
downloaded model directories and user-data backups are excluded from these
committed files and from the QA ZIP. The app packages are local development
artifacts; this commit does not publish a GitHub release or imply notarization.
