# 1.8.0 — local Windows test build

Private portable build for the owner's longer trial, without publishing a
release. Automated UI checks use the offscreen backend so they do not interrupt
desktop use. Interactive Windows/game testing remains part of the trial.

- Fresh installs and Reset use the light theme, show Kirby in the main menu,
  enable hover tips and launch-time update checks, and disable copy notifications.
  Standard hotkeys are retained. Translation targets follow the chosen interface
  language until the corresponding language pair is customized. Existing saved
  preferences survive upgrades.
- Welcome and update news briefly introduce 1.8.0 and thank users for 3,000
  downloads. The previous free-forever promise and lengthy changelog are removed.
- Embedded dropdowns fit inside the fixed main window, including the multiple
  choice result-window control. The Companion page no longer has the redundant
  Display heading or explanatory paragraph.

- The main-window mascot uses the spare shortcut cell without shrinking the text
  editors, and walks while the main window is inactive. A separate native dialog
  offers settings or dismissal. The Companion settings page restores visibility.
- Companion settings fit on one page, with regular checkboxes and numeric fields
  instead of a toggle and sliders. All visibility checkboxes share one column.
  Pick Dynamic or Static, then an image; movement controls only appear for Walking
  Kirby. The main-menu walking sprite remains enabled by default. The desktop
  popup's Open translator action opens the separate editable translation window.
  The desktop popup contains translation actions
  and Hide only, with no tabs, preferences or scrolling. Rounded surfaces are clipped.
  The tray toggle uses the same ordinary action style as the other entries.
- Companion number fields select the existing value for replacement and accept
  partial typing before committing within their range. Custom artwork is reused
  when reselected; Replace opens the file picker. Image failures identify the
  actual cause. Native scaled JPEG decoding allows up to 64 MP, other decoders
  keep the 32 MP limit; all retain the 10 MB / 8192 px bounds. Only one custom
  thumbnail of at most 512 px is cached.
- General and translation-window scale controls use the same horizontal arrows
  and centered editable percentage, changing by one percentage point per click.
  Companion and dynamic-output numeric fields share that presentation and retain
  their ranges and keyboard entry. Document context actions stay on the main
  screen and no longer appear when right-clicking Companion settings.
- Shortcut-reference rows explicitly clear hover when focus leaves the window.
  OCR/update checkbox rows use the same height and spacing as General.
- Dynamic translation places output next to selected text by default; manual
  placement remains optional. One toolbar manages all outputs, with inline
  optional formatting and template saving. Selection only loads saved templates;
  the existing template format is preserved.
- Button hover tips move to the compact left preference column. FAQ social links
  use Telegram and GitHub icons. Help uses the app's flat palette, a compact
  heading and a single footer for social links, diagnostics and the guide.
  Theme conversion preserves the contrast of pressed scrollbar handles.
- The settings gear is drawn as a vector in every icon state, without depending
  on a separate PNG. Rounded native dialogs clip to their visible content frame.
- Windows shortcut fields accept two short taps of one key, such as Shift → Shift
  or F8 → F8. Holds, auto-repeat, chords, injected input and switching foreground
  windows cancel the gesture. The optional shared keyboard hook never consumes
  key events and runs only while a double-tap shortcut is assigned. Existing
  combinations retain their normal registration path. Other platforms retain
  their existing shortcut support.

The earlier translation-window engine override, welcome links/checkbox,
capture-language labels and portable manifest-folder changes are retained.

Validation on Windows, 2026-09-23:

- Complete isolated-data regression run: 1,624 passed, 60 skipped, 911 subtests
  passed; exit 0 and real user data unchanged. Skips cover other platforms and
  unavailable Inno Setup/Windows SDK tools. An additional Companion interaction
  run passes all 28 tests, including independent main/desktop visibility.
- Offscreen dropdown bounds and text widths pass in six languages, both themes
  and scales 80–200%. Shared numeric controls and principal layouts were rendered
  and inspected in both themes.
- The packaged launcher starts the actual frozen GUI offscreen, verifies its
  complete manifest, and acknowledges version 1.8.0. A disposable fresh profile
  has the requested defaults. Packaged Argos imports/probes successfully; the OCR
  worker's JSON/error protocol works. This does not claim an end-to-end OCR or
  online translation check in a game.
- All 4,022 program files pass the manifest check. The portable ZIP passes CRC
  validation, retains the hidden compatibility manifest, and contains no personal
  data. This is an unsigned local portable build, not a published release.
- The preview uses 69,120 bytes of cached sprite pixels. In the offscreen sample,
  animation repaints at most 0.315% of the viewport per tick and stops completely
  while hidden/minimized. Native CPU usage while gaming is left for the trial.

Artifacts: `releases/ClicknTranslate-v1.8.0-win64-test-20260923/ClicknTranslate/`
and `releases/Click-n-Translate-1.8.0-windows-portable-x64-test-20260923.zip`.
