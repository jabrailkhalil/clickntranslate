# Validation

The settings/update follow-up at source `efdabcd` passed **2073 tests and 915
subtests**, with **77 skipped and zero failures/errors** in the selected final
eight partitions (part 3 replaced after updating a brittle source-prefix check).
Every selected run kept user data unchanged. See
[`settings-update-validation.json`](../../settings-update-validation.json) and
[development scope](../../UPDATES_1.8.2_DEVELOPMENT.md). Native Mac/Linux GUI
replacement still needs its platform runner. Five real Inno installation cases
were skipped; automatic approval review blocked installing the missing compiler.
Windows portable replacement and rollback exercised the compiled quiet helper.

## Earlier validation

The latest source at `84e166a195802380ab03776bc90dfcdf1e88ba2e` uses the actual
hotkey row for the home mascot: caption left, cached thumbnail right, with the
same typography, padding and pointer states. The offline-translator follow-up
adds pair/model checks, actionable localized prompts, direct installer tabs,
explicit ready-provider selection and structured worker setup failures. Cancel,
close and installation navigation preserve drafts and keep local choices scoped
to their window. A standalone result can open a settings host with background
services disabled; its close path leaves other windows and active modes alone.

Final eight-part results, including replacement runs for parts 3, 4, 5 and 8:
**2039 passed, 77 skipped, 919 subtests passed and the same 2 pre-existing version
metadata failures**. Final focused navigation/provider/hover checks passed
**160 tests and 24 subtests**. Every selected isolated run kept user data
unchanged. Older tests were updated to accept the newly requested mascot prompt
and to declare local providers installed when testing backend dispatch. The
initial runs stopped at those previously implicit interactions; the final
replacement runs completed. See `ui-recovery-validation.json` for exact partition
results. The full suite was run offscreen on Windows; native macOS execution and
release packaging were not performed for this follow-up.

The subsequent home-shortcut follow-up restores the localized Mascot caption
and offers the same styled settings prompt as hotkey rows. Its primary action
opens the mascot carousel; rejecting or closing preserves the main-window
draft. It passed **73 checks and 26 subtests**, including real modal interaction
and primary-button text fitting in all six languages. The static preview still
uses its cached thumbnail and no animation timer. This was a focused UI run;
the earlier full-suite results below are retained separately.

The latest local UI follow-up reproduced the Reset hover bug at 80%, 125% and
180%, and the package scrollbar/header overlap at two header heights before
fixing them. Global button hover now maps through the actual proxy viewport;
native hover flags, press state and mouse focus are cleared without losing
intentional keyboard focus. The five general-settings fields share their box
insets and value font, and drop-downs use the stepper glyph rotated down.

The complete eight-part run plus the final replacement of part 6 produced
**1992 passed, 77 skipped and the same 2 pre-existing version failures**. The
initial part-6 pixel assertion was corrected to allow Qt's one-pixel fractional
proxy rounding; its final run passed **290 checks and 11 subtests**, with 9
native-only skips. A final cross-control run passed **110 checks and 26
subtests**. It covers six languages, both themes, actual painted field bounds,
matching value fonts, bounded arrows, ordinary-button hover cleanup and dynamic
toolbar scaling. The existing dynamic toolbar retains its 15px font while the
main settings use 14px throughout their right column. Another **60 hidden native
Windows label measurements** passed. Hidden dialog rendering at 80%, 100% and
150% confirmed that scrollbar tracks start at the row viewport below the
header. All completed isolated runs kept user data unchanged. The source app
was opened for review; no build, push or release was made. Android remains in
the separate agent's scope. The immutable earlier source-commit records below
and in `test-summary.json` are retained.

The unpublished settings follow-up puts Scale directly below result visibility,
followed by a named result-text arrow control and its live sample. It passed
**136 checks, 1 native-only skip and 167 layout subtests**, covering six locales,
both themes, bounded mouse/keyboard steps, live result updates and selection
cleanup. Another **60 native Windows font/label measurements** passed without
showing test windows. The prior complete-suite record below is unchanged; no
release, push or PR update was made for this local follow-up.

The next local follow-up reproduced both mouse-click endpoint highlight bugs
before fixing them. Disabling an arrow now clears mouse focus/hover first,
preventing Qt from assigning false Tab focus to its neighbour. Actual keyboard
input still retains keyboard focus. The sample has a theme-aware frame with
padding, checked against the largest text's available content area. These
changes passed **112 checks and 167 layout subtests** with user data unchanged.

All six exact encoded Pets v2 atlases retain their structural, visual-quality,
blind direction and Pets MCP acceptance records. This UI update does not modify
or regenerate artwork.

The complete suite ran with the bounded, isolated repository runner:

```
python tools/run_ci_tests.py --parts 8 --timeout 160
```

Full-suite results at `eae52e40a3e4087b91d7eb41977ebe8bf6fc9457`:
**1981 passed, 77 skipped, 2 pre-existing version failures**. The final compact
numeric font choices and current-size tooltip at `688a51e928140a6d5c541bcfa2e78f3fafeddf3d`
then passed **80 focused checks, 1 native-only skip and 26 layout subtests**.
Latest focused native Windows checks: **35 passed** on two physical monitors.
They exercise the real `QMenu.exec_` loop, rather than replacing it with
`popup()`, after moves in both directions at 80%, 100% and 150%. This reproduces
and prevents the original primary-monitor clamp for flag, editor and background
menus. Real successive hover delivery and the global off switch are tested on
both screens; all five font sizes and all six locales fit their live preview.
Earlier native animation checks: **58 passed**; integrated native monitor/focus/
control checks: **54 passed**. See
`test-summary.json` for the complete eight-part run. The only remaining failures
are the two development-version metadata checks described below. Every completed isolated run reported
`USER_DATA_UNCHANGED: True`.

An earlier extended native batch passed 135 checks but lost a held-arrow click
once during its longer window/focus sequence. The isolated four-check rerun and
the final 35-check native run both passed, including that held-arrow check.
The complete offscreen suite also passed it. Native rapid-theme/navigation
paint and atomic theme-transaction checks passed in the extended batch; those
fixtures deliberately expose individual palette states while running visibly.

PR #7 was corrected on its own head and merged at
`be5c5350586fd3086269d76c72592712bef20668`. Its exact fixed head
`e704dfa257e919404a41c98fa0813b7dd25273c1` passed the complete suite:
**1769 passed, 67 skipped, no failures**. The development mascot branch includes
that merge and was tested again with the integrated changes.

Coverage includes:

- One selected static home shortcut opens mascot settings directly. Tiny cached
  PNGs avoid atlas decoding and a repaint timer; draft/control identity survives
  navigation and cache invalidation handles configuration and layout changes.
- Same-fixture navigation profiling includes actual Qt event processing. Repeat
  returns changed from 99–100 ms to 5–6 ms locally; see
  `navigation-performance.json` for complete measurements and their limits.
- Native automatic reactions with no walking or manual emotion picker.
- Previous/next carousel arrows, wrapping, keyboard navigation, a name above
  each character and a sliding platform; rapid clicks finish consistently.
- Checkbox column on the left and three right-side fields in six languages,
  in both themes and at different scales. No duplicate character dropdown.
- Native Qt stage rendering, event reactions, and animation/timer cleanup on
  hide, minimize and resize.
- Every native animation frame and all sixteen gaze directions for each of the
  six characters render identically over reused and fresh transparent surfaces.
  The alpha clear prevents old pose fragments from persisting around Doc.
- Doc's malformed idle ankle frames are excluded consistently at compact,
  settings and desktop sizes. The remaining clean resting/raised frames keep
  genuine animation and the original cycle timing. Legacy idle poses also use
  the clean frame; all other characters/reactions/gaze rectangles are unchanged.
- Numeric draft commits and text deselection on background clicks inside the
  real scaled graphics canvas; copying an existing text selection still works.
- Arrow mouse focus, stale native hover, Tab focus, and deactivation cleanup,
  including tests using the Windows Qt backend rather than only offscreen Qt.
- Rectangular language package frames, themed active/inactive row selection,
  absence of a native dotted cell focus box, and fitted columns after font changes.
- Opt-in select-all before replacement: off by default, setting persistence,
  six-language layout, operation order, target validation, key release and an
  unchanged ordinary-selection action. Existing verified-selection replacement,
  clipboard restoration, capture ownership and cancellation tests also pass.
- Popup placement through the scaled graphics canvas at 80/100/150 UI scales,
  positive/negative monitor origins and screen edges. Native Windows checks
  actually moved the window and opened its flag menu on both connected screens.
- Quick selection worker responsiveness, bounded probe coalescing, cancellation,
  foreground changes, cleared selections and fresh validation on button clicks.
  The Ctrl+C fallback restores previous clipboard text, including empty text,
  even when copying fails; keyboard cleanup is checked independently.
- Three-agent audit of six-language labels, tooltips and accessibility names in
  main/settings, capture/dynamic/OCR, shared dialogs, startup and mascots. Close
  differs from home/back/cancel; pause becomes resume, undo removes the last
  selection, and standard dialog buttons follow the application language.
  Dictionary keys and formatting placeholders match across all six languages.
- Newly created quick-selection checkboxes and radio controls have visible
  indicators and distinct checked/unchecked states in both themes.
- The four general-settings dropdowns precede the bottom scale control, with
  aligned checkbox/field rows in both themes and all six languages. Numeric font
  choices identify the result-text size, with a live sample underneath and
  full descriptions on hover. Even the 24px sample retains its descenders.
- Dedicated six-language hints and shared complete-label fallbacks cover every
  visible interactive control on home, four settings tabs and hotkeys. A single
  hover timer bridges proxy controls using native viewport coordinates; moving,
  leaving, dragging and disabling hover help do not retain the previous hint.
- The repository audit reads tracked text even when absent from the sparse
  checkout. Unused research/comparison resources and obsolete development tools
  were removed; the six active atlas hashes are unchanged. Actual OCR/model/
  build dependencies and font/library license notices are retained.
- The tracked landing page builds in a new isolated directory: six localized
  pages, 31 public files and the retained font license. No site was deployed.

Remaining failures exist in unchanged base commit
`959175faefcd4b7591d0d91fde5535785d155ae5`:

- `test_release_version_is_synchronized_everywhere` hardcodes 1.8.1 while
  `app_version.py` declares 1.8.2.
- `test_latest_metadata_release_matches_the_application_version` compares 1.8.2
  with the existing AppStream 1.8.1 development release entry.

Release metadata and those two tests are unchanged. Installers and macOS/Linux
builds were not produced. Provider/OCR callbacks and foreign-window key handling
used deterministic fixtures without sending text to other apps or requesting
translations online. macOS Cmd+A support reuses the existing focus-validated
native shortcut helper; it was not exercised on a physical Mac.

The source app was launched with `python tools/run_mascot_app.py` without
packaging, using its own review profile. Global hotkeys, translation and opt-in
quick selection are active; OS autostart changes and tray creation are disabled
for this review copy. Actual Qt screenshots of both themes, mascot settings,
general/hotkey settings, the static home shortcut, language tables and desktop
popup were visually reviewed. No user screenshots or personal data were committed.
