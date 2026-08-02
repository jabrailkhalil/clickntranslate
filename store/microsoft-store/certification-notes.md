# Notes for certification

Click'n'Translate is a user-invoked Windows screen OCR and translation utility.

- The application runs as a full-trust desktop process because it registers global hotkeys, captures a screen region selected by the user, reads/writes the clipboard on request, and starts optional OCR/translation worker processes.
- `CreateProcess`/`ShellExecute` references reported by the optional WACK blocked-executable heuristic are expected: the app launches its packaged `ArgosWorker.exe` and `OcrWorker.exe`, optional locally installed OCR runtimes, Hy-MT's local runner, and user-requested browser links. It does not install or silently run command shells.
- Default hotkeys are Ctrl+Alt+C (OCR to clipboard), Ctrl+Alt+T (OCR and translate), Ctrl+Alt+F (full-screen translation), and Ctrl+Alt+Q (selected-area translation). All hotkeys can be changed in Settings.
- Online translation engines send only the text the user asks to translate to the selected provider. Offline Argos and Hy-MT engines process translations locally after packages are downloaded.
- Windows OCR, Tesseract, RapidOCR, and EasyOCR process images locally. Optional engine and language packages are downloaded only after a user action.
- The application has no account system, advertising, analytics, or telemetry.
- “Start with OS” is off by default and is enabled only after the user selects the checkbox.
- Store builds do not self-update from GitHub. The Update button opens the Microsoft Store updates page.
- The main executable declares Per-Monitor V2 DPI awareness. NumPy's upstream test directories and compressed test fixtures are excluded from the Store package.

Basic test flow:

1. Launch the app and keep the default Windows OCR and Google translation engines.
2. Press Ctrl+Alt+T, select an area containing text, and confirm that the translation window appears.
3. Open Settings → Language packages to inspect optional OCR and Argos packages.
4. Open Settings → Configure hotkeys to inspect or change all four bindings.
