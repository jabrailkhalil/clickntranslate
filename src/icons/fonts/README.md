# Linux interface font

The unmodified Liberation Sans regular and bold faces provide consistent metrics
when Segoe UI is unavailable on Linux. Qt registers them once before constructing
the interface; no runtime download or system font installation is required.
Windows and macOS keep their existing font selection.

Source: Ubuntu package `fonts-liberation2` version `2.1.5-1`, upstream
<https://github.com/liberationfonts/liberation-fonts>. The complete package
copyright and SIL Open Font License 1.1 are retained in
`LIBERATION-LICENSE.txt`. Font names and outlines are unchanged.

SHA-256:

- `LiberationSans-Bold.ttf`: `ba0e0dc3f7aca5b0afbc31e800531ee43be3aa79ae35b2ef1f6470a9547765c4`
- `LiberationSans-Regular.ttf`: `8d91388f1d3604b3b8ae0e3ee2d140e50cd6122f9214514f4aca772540a4076d`

## Hindi fallback

The unmodified Noto Sans Devanagari regular and bold faces are registered once
only when Qt finds no system font supporting Devanagari. This keeps Hindi labels,
tooltips and guides readable on minimal installations, without a runtime download.
The existing Latin interface font is retained.

Source: [Noto Devanagari](https://notofonts.github.io/devanagari/), hinted TTF files,
retrieved on 2026-10-24. The complete upstream SIL Open Font License 1.1 and
copyright notice are retained in `NOTO-DEVANAGARI-LICENSE.txt`.

SHA-256:

- `NotoSansDevanagari-Regular.ttf`: `6600a318c94f6c7d5d6ea6e0133c017748c6449f426558adb9691747d2165613`
- `NotoSansDevanagari-Bold.ttf`: `68ad1dc7aed6ff8d8ea32414aaca0039c47dad57f019e9a108adc0f63386b991`
