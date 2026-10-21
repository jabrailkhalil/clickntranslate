# Validation

All six exact encoded Pets v2 atlases retain their structural, visual-quality,
blind direction and Pets MCP acceptance records. This UI update does not modify
or regenerate artwork.

The complete suite ran with the bounded, isolated repository runner:

```
python tools/run_ci_tests.py --parts 8 --timeout 120
```

Full-suite results: **1834 passed, 67 skipped, 2 pre-existing
version failures**. The focused replacement/settings/text-controls group passed
**111 tests**. Final native Windows checks passed **38 tests**, including an
additional application-deactivation case. Latest combined results are
**1835 passed, 67 skipped, 2 unchanged version failures**.
Every run reported `USER_DATA_UNCHANGED: True`.

Coverage includes:

- All six characters in the main-window row; each opens mascot settings directly
  without opening the desktop popup or enabling an overlay.
- Native automatic reactions with no walking or manual emotion picker.
- Previous/next carousel arrows, wrapping, keyboard navigation, a name above
  each character and a sliding platform; rapid clicks finish consistently.
- Checkbox column on the left and three right-side fields in six languages,
  in both themes and at different scales. No duplicate character dropdown.
- Native Qt stage rendering, event reactions, and animation/timer cleanup on
  hide, minimize and resize.
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
- Shared compact main-row atlases below 6 MiB; native frames and custom images.

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
packaging, using its own review profile. Actual Qt screenshots of both themes,
mascot settings, general settings, the main row, language tables and the desktop
popup were visually reviewed. No user screenshots or personal data were committed.
