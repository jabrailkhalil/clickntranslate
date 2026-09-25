# Local 1.8.0 UI follow-up — 25 September 2026

Source fixes after the owner's Windows trial:

- Welcome Telegram/GitHub icons choose contrasting colours from the active
  theme. The language menu has a clipped native shape, aligns below the flag,
  and keeps all six entries inside the screen.
- The main send arrow has no button tile on hover, press or keyboard focus.
- Dynamic selection hides the template picker when no saved layout exists.
  “Don't overlay on text” moved to Dynamic settings. The new toolbar checkbox
  hides/shows the running session's controls without ending its translation.
- The trial log showed successful OCR and a Google HTTP 200 response but no
  displayed translation. The session had bound to an invisible Explorer window,
  causing automatic pause after the startup focus grace period. Windows now
  resolves the window underneath the chosen source after the selector closes
  and returns focus to it. In-place output also follows the source when moved.

## Verification

- Focused isolated-data regression: **173 passed, 1 skipped, 12 subtests passed**.
  The skip requires native macOS AppKit. User-data hashes were unchanged.
- Settings bounds and label widths passed in all six UI languages and both
  themes. Native Windows welcome-menu checks passed in both themes, including
  complete action rectangles and transparent corner pixels.
- `python tools/qa_windows_dynamic_region.py` passed with a separate Windows
  process displaying generated text. Actual Windows OCR recognized both frames;
  the correct source HWND stayed active past the startup grace period, translated
  output covered the source, and updates continued with the toolbar hidden.
  Translation in this deterministic check is a stub; no production provider
  request or game integration is claimed by this check.
- Preview images and reports are under `.tmp/qa-followup-previews/`,
  `.tmp/qa-followup-regression/`, and `.tmp/qa-native-region/`.

The Python source version was restarted for the owner's trial. No packaged EXE,
commit, tag, push or published release was produced.
