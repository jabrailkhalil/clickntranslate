# Validation

All six exact encoded atlases retain their original structural, visual-quality,
blind direction and Pets MCP acceptance records. No artwork was regenerated for
the stationary interaction update.

The complete suite ran with the bounded, isolated repository runner:

```
python tools/run_ci_tests.py --parts 8 --timeout 120
```

Latest combined results after final focused rechecks: **1801 passed,
67 skipped, 2 pre-existing version failures**. The focused mascot,
interface and cache group passed 226 tests; the final settings checks passed
28 tests, and real popup keyboard selection/stationary cache checks passed 2.
All runs reported `USER_DATA_UNCHANGED: True`.

Coverage includes legacy walking-profile migration, zero travel at any saved
speed/size, seven native animation rows only, all six characters, 16-way gaze,
click greeting, one-cycle reactions, static-pose restoration, real dropdown
keyboard selection, menu placement, six languages/two themes, capture ownership,
concurrent translation jobs, cancellation and stale-result guards. Whole-frame
playback uses shared cached PNGs; picker thumbnails retain only one cell.

Remaining failures exist in unchanged base commit
`959175faefcd4b7591d0d91fde5535785d155ae5`:

- `test_release_version_is_synchronized_everywhere` hardcodes 1.8.1 while
  `app_version.py` declares 1.8.2.
- `test_latest_metadata_release_matches_the_application_version` compares 1.8.2
  with the existing AppStream 1.8.1 development release entry.

Release metadata and those tests are unchanged by this PR. Native installers
and macOS/Linux builds were not produced. Qt regression/layout checks used the
Windows Python environment with the offscreen backend; provider/OCR callbacks
used deterministic fixtures without network requests. The actual source app was
also opened using `python tools/run_mascot_app.py`, without packaging.

The settings, fixed-position companions and compact action popup were rendered
from real Qt widgets for visual review. `stationary-v2.gif` and
`native-emotions-v2.png` show only the seven native stationary states.
