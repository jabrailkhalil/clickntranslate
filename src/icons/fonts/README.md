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

## Simplified Chinese fallback

Qt registers the two ClicknTranslate Han faces when the system has no font for
Simplified Chinese. Each face contains the Han characters, East Asian punctuation
and native language names used by the application. For arbitrary input and
translations, additional characters require a system font that contains them.

The outlines come from Noto Sans CJK SC 2.004, copyright © 2014–2021 Adobe.
These OFL 1.1 derivatives use the family name ClicknTranslate Han and retain
the upstream copyright, authorship and license metadata. The full license
is in [NOTO-CJK-LICENSE.txt](NOTO-CJK-LICENSE.txt). The original
[regular](https://github.com/notofonts/noto-cjk/blob/523d033d6cb47f4a80c58a35753646f5c3608a78/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf),
[bold](https://github.com/notofonts/noto-cjk/blob/523d033d6cb47f4a80c58a35753646f5c3608a78/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf)
and [license](https://github.com/notofonts/noto-cjk/blob/523d033d6cb47f4a80c58a35753646f5c3608a78/LICENSE)
are pinned to the same upstream revision.

| Face | Upstream SHA-256 | Bundled SHA-256 |
| --- | --- | --- |
| Regular | `2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b` | `e13166f1b4bec206a3c0552429030f925cd5f7772647f301d2cfbcbf0b858f98` |
| Bold | `b5f0d1a190a7f9b43c310a8850630af12553df32c4c050543f9059732d9b4c0a` | `467906d8cf04d67dc20b9f7d68909326689664d62dc2a119fc736879cad28999` |

To regenerate the faces, place both original OTFs in the same directory and
run `python tools/build_chinese_ui_font.py <source-directory>` with
`fonttools==4.59.2` installed. The builder verifies the input hashes and
collects characters directly from the Python interface sources. The test in
`tests/test_bundled_script_fonts.py` checks both output faces against that corpus.
