# Validation

All six exact encoded Pets v2 atlases retain their structural, visual-quality,
blind direction and Pets MCP acceptance records. This UI update does not modify
or regenerate artwork.

The complete suite ran using the bounded, isolated repository runner:

```
python tools/run_ci_tests.py --parts 8 --timeout 120
```

Final full-suite results: **1810 passed, 67 skipped, 2 pre-existing
version failures**. The focused mascot/interface/cache/layout group passed
**251 tests**. Every run reported `USER_DATA_UNCHANGED: True`.

Coverage includes:

- Six characters in one stationary main-window row; each opens mascot settings
  directly without opening the desktop popup or enabling an overlay.
- No manual emotion picker in the desktop menu or settings; real application
  actions drive seven native animation states, with active work taking priority.
- Checkbox column on the left and aligned right-side fields in six languages;
  popup reachability and layout at different scales and in both themes.
- Themed preview scene, native click jump, live activity feedback and timer
  shutdown when hidden/minimized; the event-reaction preference applies to it.
- Shared compact atlases below 6 MiB total for the main row, without per-frame
  loading; whole-frame native playback, 16-way gaze and legacy-profile migration.
- Capture hiding, concurrent translation jobs, cancellation and stale-result
  guards; native static poses and custom-image compatibility.

Remaining failures exist in unchanged base commit
`959175faefcd4b7591d0d91fde5535785d155ae5`:

- `test_release_version_is_synchronized_everywhere` hardcodes 1.8.1 while
  `app_version.py` declares 1.8.2.
- `test_latest_metadata_release_matches_the_application_version` compares 1.8.2
  with the existing AppStream 1.8.1 development release entry.

Release metadata and those two tests are unchanged by this PR. Native installers
and macOS/Linux builds were not produced. Qt regression/layout checks used the
Windows Python environment with the offscreen backend; provider/OCR callbacks
used deterministic fixtures without network requests. The source app was also
launched with `python tools/run_mascot_app.py`, without packaging.

Real Qt screenshots of the general settings, redesigned mascot settings, both
themes, six-character row and desktop action popup were visually reviewed.
