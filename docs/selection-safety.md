# Selected-text input safety

## Passive detection

The floating selection button and automatic translation read through the OS
selection API. Their initial probe and button recheck must never synthesize
Ctrl+C, Ctrl+A or Ctrl+V, nor clear or restore the clipboard. Missing UIA
support, a caret without selected characters and a provider failure all mean
that no automatic action is taken. The Windows reader does not substitute
an element's Name or Value for selected text. Password controls are excluded.

## Explicit commands

The selected-text hotkey and companion action keep copy-key compatibility for
applications without readable text selections. This happens only after an
explicit request. On Windows the source HWND is captured before the worker
starts and rechecked around capture so a delayed request cannot silently
switch to a different foreground application.

## Replacement

Windows replacement requires a focused, enabled, non-password text editor.
UIA must confirm writable Value/Text content in an Edit or editable ComboBox.
A Document additionally needs the TextEdit pattern: the default IsReadOnly
attribute by itself is not proof of an input field. Grid cells and other
non-editor control types are excluded.

The source HWND, process and opaque UIA runtime ID form a per-request editor
identity. Both select-all and replacement verify this identity. Before paste,
the existing copy/compare check also verifies that the selected source text
has not changed. A different field within the same application is a different
target. An unsupported or inaccessible provider cannot authorize a shortcut.

If no editor can be confirmed at capture time, the app displays a localized
explanation and sends no replacement keys. If the target becomes invalid
after translation, the finished translation uses the existing clipboard/result
fallback. Clipboard restoration preserves newer user copies.

UIA preparation is lazy on the GUI thread; operations and owned COM apartments
run on workers. Only primitive editor identity crosses an apartment boundary.
No OCR/model warmup, new native dependency or replacement GUI is introduced.
The macOS Accessibility and Linux PRIMARY paths remain platform-specific.

## Verification

Run the isolated regression runner with the default offscreen platform:

```text
python tools/run_regression_tests.py tests/test_passive_selection_safety.py tests/test_windows_uia_contract.py tests/test_selection_probe_safety.py tests/test_selection_clipboard_preservation.py tests/test_replace_select_all.py tests/test_companion_selection_target.py
```

These tests use simulated UIA providers, input, clipboard and translation
responses. They cover no selection, unsupported providers, password/read-only
controls, grid cells, field/window changes, replacement and COM lifetime.
They do not certify a particular third-party application's UIA implementation.
Interactive editor/browser/Excel/terminal checks require a separate, explicitly
permitted native test session; never run them while the user is working.
