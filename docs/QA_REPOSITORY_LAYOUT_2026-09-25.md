# Repository layout verification — 2026-09-25

## Scope

The source tree was reorganized from 91 root entries to 17: five directories
(`.github`, `docs`, `src`, `tests`, `tools`) and twelve root files. The root
`main.py` entry point and `app_version.py` remain in place.

The English, Russian, Spanish, French and Simplified Chinese READMEs now include
the supplied companion screenshots in both themes and the dynamic translation
region-selection screenshot. Existing demo GIFs and hotkey tables were retained.

Implementation commits:

- `599d8e016995f81db866f28c327f7607ecf2168d`: relocation, path adaptations,
  documentation and regression coverage.
- `9c951c5`: corrected the relocated AppStream input in Linux packaging;
  verified by building and launching the resulting AppImage locally.

## Results

| Platform / check | Result and scope |
| --- | --- |
| Windows and Linux CI | Full configured suites passed in [run 36174011578](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36174011578), at commit `599d8e0`. |
| Windows packaging | PyInstaller build completed; the staged launcher, application, private workers and program inventory were checked. |
| Windows 1.7.0 migration | The original released 1.7.0 updater installed the private build from the reorganized source. All 3,956 package files matched, preferences and three synthetic data/model markers survived, and the application acknowledged startup and launched again. |
| Linux native packaging | The executable, tar archive and AppImage were built on Ubuntu 22.04. The executable and AppImage both reported GUI readiness in an isolated offscreen session. Both source-test shards passed and reported unchanged user data. |
| Mac Apple Silicon | Native app, DMG and ZIP built. Cocoa GUI, settings, Vision recognition, Carbon registration, RapidOCR and Argos helper checks passed. All 228 Mach-O files passed the macOS 13.4 compatibility check. Both source-test shards passed and reported unchanged user data. |
| Mac Intel | Native tests, build and smoke checks passed in [run 36174006602](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36174006602), at commit `599d8e0`. |
| Research paper | Relocated paper compiled and its PDF artifact uploaded in [run 36173918342](https://github.com/jabrailkhalil/clickntranslate/actions/runs/36173918342). |

Initial checks exposed old path assumptions in tests, missing store screenshots
in the Mac/Linux source export, and an old AppStream path in Linux packaging.
These were corrected before the successful reruns above.

## Update evidence and limits

The Windows migration used the released updater without a helper override:

| Input | SHA-256 |
| --- | --- |
| Released Windows 1.7.0 portable ZIP | `1aaee222b1d1d3024b022f9187e762719ea8582cd9dd56fd34ba19bf12c12528` |
| Original 1.7.0 updater invoked in the check | `884d61961d439b30b6a7c0a990f9d9b3c56b541c9fdfd229321f661d2b358cfa` |
| Private Windows layout QA ZIP | `516009c66c17604f5e657577d1a77ae6320e3ef02207155aab81e9d14c50de1b` |

The machine-local receipt is
`build/update-audit/repository-layout-170-zip/result.json`. This exercises the
old updater command-line handoff and real application processes; it does not
automate the download/update-button flow. The running Windows Python app was
temporarily closed with the user's approval and restarted after the check.

Mac builds used development ad-hoc signing. This verification does not certify
notarization, production signing, every desktop/capture environment, or a fresh
Mac/Linux upgrade from an older installed version.

## Published release remains unchanged

No version bump, release publication, tag change or public asset replacement was
performed. All new packages are isolated QA artifacts, still carrying the source
version `1.8.1`; they are not the downloadable public 1.8.1 packages.

The published `v1.8.1` tag remains at
`60490b572f915f46c9a95f930f5573154f8b27ee`. Its eight assets retain their existing
names and SHA-256 digests. The updater sources, acknowledgement/inventory
protocol, packaged names and user-data locations were preserved.
