# Validation

All six exact encoded atlases passed bundled structural and visual-quality
gates, independent blind cardinal review and Pets MCP preflight. Native-size
contacts, direction sheets, animation GIFs/MP4 and idle-jump-idle transitions
were reviewed. The actual Qt application was rendered with an isolated profile
to check the six-character selector, settings and both companion views.

The full test suite ran with the repository's bounded, isolated CI runner:

```
python tools/run_ci_tests.py --parts 8 --timeout 120
```

Updated UI/cache test files and existing store/readme fixtures were rechecked
after the initial full run. Latest combined results: 1789 passed, 67 skipped, 2 pre-existing version failures.
The focused mascot/interface/cache group passed all 171 tests. Every isolated
run reported `USER_DATA_UNCHANGED: True`.

Remaining failures exist in the unchanged base commit
`959175faefcd4b7591d0d91fde5535785d155ae5`:

- `test_release_version_is_synchronized_everywhere` hardcodes 1.8.1 while
  `app_version.py` already declares 1.8.2.
- `test_latest_metadata_release_matches_the_application_version` compares that
  1.8.2 version with the existing 1.8.1 AppStream development release entry.

Release metadata and the release-version test are unchanged by this mascot PR.
Native installers and macOS/Linux GUI builds were not produced. Qt UI checks
used the Windows Python environment with the offscreen backend; translation
and OCR callbacks used deterministic fixtures without network requests.
