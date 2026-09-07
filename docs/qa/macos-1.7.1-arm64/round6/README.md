# Native macOS window placement — 7 September 2026

Real Cocoa on Apple M1, macOS 14.3, Retina DPR 2. The source and the installed
DMG copy each passed 48 independent center/bounds assertions: eight dialog types,
both themes, and 80/100/130% scale. First main-window placement is also asserted.
`positions-before.json` and `positions-after.json` record the original displaced
owner probe; `installed-smoke.json` contains the installed application's matrix.

Full native suite: 1060 passed, 72 skipped, 892 subtests. The intermediate failure
in `targeted-tests.txt` was an artificial screen origin overlapping the real macOS
menu bar. The test retains its size/scale assertions and now uses the real available
origin. `position-regressions.txt` and the full suite show the corrected outcome.

PNG files are selected installed Qt window buffers; they verify rendering, while
native desktop placement is checked numerically. Full source/installed images and
scripts are in the local QA archive linked from `docs/MACOS_QA.md`.

The application was rebuilt, installed from a read-only DMG, verified, and started
normally; the second autostart instance exited successfully. User data and the old
application were preserved. Carbon dispatch, Vision and the frozen RapidOCR/Argos
helpers passed. This does not substitute for physical keyboard/mouse/Dock tests.

Screen capture succeeded in the prior installed process after the permission repair
(`prior-installed-capture.json`, metadata only). The new ad hoc signature changed
identity again: the final installed preflight reports screen/accessibility false.
No TCC reset, Gatekeeper bypass or new trusted certificate was applied this cycle.
The binary is ad hoc signed and not notarized; Gatekeeper rejects it.
