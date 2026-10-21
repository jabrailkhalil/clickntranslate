# Validation

All six exact encoded Pets v2 atlases retain their structural, visual-quality,
blind direction and Pets MCP acceptance records. This UI update does not modify
or regenerate artwork.

The complete suite ran with the bounded, isolated repository runner:

```
python tools/run_ci_tests.py --parts 8 --timeout 160
```

Final full-suite results: **1967 passed, 68 skipped, 2 pre-existing version
failures**. Latest native Windows settings checks: **31 passed, 26 subtests**.
Earlier native animation checks: **58 passed**; integrated native monitor/focus/
control checks: **54 passed**. See
`test-summary.json` for the complete eight-part run. The only remaining failures
are the two development-version metadata checks described below. Every completed isolated run reported
`USER_DATA_UNCHANGED: True`.

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
  aligned checkbox/field rows in both themes and all six languages. Font-size
  help describes the separate result window and the difference from UI scale.
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
