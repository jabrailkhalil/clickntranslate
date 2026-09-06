# Editable translation window (1.7.1)

The result window now keeps the source and translation visible together. It
uses two columns in a wide window and stacks the fields when narrowed. Both
fields accept plain-text editing with independent undo; long lines, including
unbroken words and URLs, wrap inside their own scrollable editor.

The language selectors belong to their respective fields. Swap exchanges both
languages **and the current edited texts**, then translates the new source.
Typing does not automatically send text to a provider. The Translate button and
Ctrl+Enter (Command+Enter on macOS through Qt's native mapping) translate the
current source; ordinary Enter inserts a new line. Copy always copies the
current output. Editing source and output no longer requires changing tabs or
guessing why the bottom action changed from Google search to translation.

Every request captures its source text, language pair and selected engine. An
edit, another language selection, a swap or closing the window cancels that
request and invalidates its response. An old answer cannot overwrite a newer
draft, create a history entry or replace the clipboard. Errors preserve both
fields; lengthy error details are available in the status tooltip without
shrinking the editors. Theme and font notifications that do not change the
text leave the draft and active request intact.

The shared appearance manager still handles global scaling, an independent
scale for this window, themed controls and fitting to the available monitor.
Manual resizing and showing the window again preserve both texts. The main
window's fixed layout and capture overlays are unchanged.

## Integration with the Mac work

Integrated on 2026-09-07 into `codex/macos-1.7.1` from commit
`c55a899a35e20f051b62e0ce75a26491b811f22a`, preserving the earlier native Mac
fixes. Cocoa testing found that stacked editors could exceed their frames at
the default font scale; the outer layout now updates the window's minimum
height when it reflows. Real Google forward/reverse requests and a controlled
LibreTranslate HTTP 503 were exercised in the native window. Drafts and the
selected provider remained intact on error. See [MACOS_QA.md](MACOS_QA.md) for
the current build, native rendering results and remaining system-level checks.

Original handoff instructions:

This change is on `codex/translation-workspace`, based on the prepared Mac
commit `d52a5f0`. It edits the result-window class in `main.py` and its tests;
native Mac integration and build scripts are not modified. The Mac agent can
fetch and cherry-pick the result-window commit onto its working branch after
saving its own changes. Check the merge in `main.py` and run:

```bash
QT_QPA_PLATFORM=offscreen .venv-macos/bin/python -m pytest -q tests/test_translation_workspace.py tests/test_translation_result_ui.py tests/test_window_appearance.py tests/test_shared_button_appearance.py
```

The native acceptance should also exercise typing, swap, Command+Enter, both
themes, resizing and Retina in a real result window. The Windows preview does
not establish native Mac behavior.

## Regression coverage

`tests/test_translation_workspace.py` checks current edited input and engine
selection, a real worker-thread response, reverse translation, independent
undo, empty input, stale responses, closing during a request, long error text,
keyboard input, six UI languages, both themes, resizing, scaling and a small
screen. Existing tests cover the main/selection/area callers, automatic copy,
per-mode language persistence, shared buttons and appearance.

Validation on 2026-09-06:

- Windows full suite: 1,058 passed, 32 skipped, 871 subtests passed.
- Windows focused UI suite after the final focus adjustment and additional
  pending-request appearance test: 79 passed.
- Ubuntu 22.04 / Qt offscreen: 182 passed, 1 skipped across the UI, translation
  chunking and Mac-support suites; all 25 workspace tests passed again after
  the final adjustment.
- Reviewed native Windows rendering and offscreen light/dark previews, including
  narrow windows. Native macOS acceptance is still required.
