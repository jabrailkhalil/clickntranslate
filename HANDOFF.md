# Click'n'Translate — 1.5.4 hotfix handoff

> **Purpose of this file.** A running, self-contained log of the hotfix work so any
> other agent (Codex, Claude, a human) can pick the work up mid-flight without re-deriving
> anything. Keep appending to it. Do not delete history — mark items done instead.

**Last updated:** 2026-08-05 — **1.5.4 released.** All three reported issues fixed and verified,
version bumped, committed, tagged `v1.5.4`, and published to GitHub. See **§11** for the release
record and **§12** for what a follow-up agent should know.
**Working directory:** `D:\1python_projects\clickntranslate-main`
**Version in tree:** `app_version.py` → `APP_VERSION = "1.5.4"`.

> **Important — the working directory is still NOT a git repository.**
> The commit and tag were made from a clean clone at
> `<scratchpad>\cnt-remote` (see §11.2), *not* from `D:\1python_projects\clickntranslate-main`.
> The two trees are content-identical apart from line endings. If you edit the working directory
> you must re-sync into a clone before committing. Consider running `git init` + `git remote add`
> in the working directory to remove this trap.

---

## 0. Scope of this hotfix (from the user)

1. **Full-screen translation is broken** — shows "Translating screen…" then nothing happens.
2. **Windows OCR language pack installation is unreliable.** Must: keep running in the
   background, report live status, and cope with packages that only appear after a long
   delay. Also: document how the Windows install mechanism actually works.
3. **The post-update window** (shown while the new version is extracted and the old one is
   removed) looks ugly. Redesign it to match the app's visual style.
4. Keep this handoff file detailed and current.
5. Publish a new release at the end.

---

## 1. Environment setup (done)

The repo had no venv and no dependencies installed. Created one:

```bash
cd "D:/1python_projects/clickntranslate-main"
python -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install "PyQt5~=5.15.11" winrt-Windows.Media.Ocr \
  winrt-Windows.Globalization winrt-Windows.Graphics.Imaging winrt-Windows.Graphics.DirectX \
  winrt-Windows.Graphics.DirectX.Direct3D11 winrt-Windows.Storage.Streams winrt-Windows.Storage \
  winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.System \
  winrt-Windows.ApplicationModel Pillow pyperclip requests psutil pypdf "setuptools<81" pytest numpy
```

`argostranslate` was added later — without it
`tests/test_argos_runtime.py::test_argos_imports_without_torch_stanza_or_spacy` fails. A second
environment `.venv311` (Python 3.11) was created for the release build; see §9 for why 3.13
cannot build a release.

Superseded note (kept for history): `argostranslate`, `pytesseract`,
`rapidocr-onnxruntime` were initially skipped. `tests/test_ocr_overlay.py` needed only
`numpy`.

Run the suite with:

```bash
.venv/Scripts/python.exe -m pytest tests -q
```

**Machine facts observed during debugging** (useful for reproducing):
- Installed Windows OCR tags on this box: `['en-US', 'ru', 'zh-Hans-CN']` → app codes `en, ru, zh`.
- Primary screen 2560×1440. `OcrEngine.MaxImageDimension` = **10000** (a full-screen grab is
  nowhere near the limit, so image size is *not* a factor in the full-screen bug).
- Full-screen WinRT OCR of the whole 2560×1440 desktop takes **~184 ms** and returns ~78 lines.

---

## 2. Issue #1 — Full-screen translation hang — **FIXED & VERIFIED**

### Symptom
Ctrl+Alt+F opens the overlay, paints "Translating screen…", and never progresses.

### Root cause (confirmed empirically, not inferred)

`ocr.py` `FullScreenOCRWorker` declared its result signal as:

```python
result_ready = QtCore.pyqtSignal(list)      # compiles to result_ready(QVariantList)
```

while the receiving slot on `FullScreenTranslateOverlay` is:

```python
@QtCore.pyqtSlot(object)                    # PyQt_PyObject
def _on_fullscreen_ocr_result(self, lines): ...
```

`QVariantList` and `PyQt_PyObject` are **not** compatible signatures, so this line inside
`_start_ocr()` raises at connect time:

```python
worker.result_ready.connect(self._on_fullscreen_ocr_result)
# TypeError: decorated slot has no signature compatible with FullScreenOCRWorker.result_ready[list]
```

`_start_ocr()` is reached from `_restart_translation_from_controls()`, which the constructor
schedules via `QtCore.QTimer.singleShot(0, ...)`. Order of operations inside that method:

```python
self.loading = True          # ← overlay will paint "Translating screen..."
self.translated_blocks.clear()
self.error_message = None
self.update()                # ← schedules the repaint
self._start_ocr(...)         # ← raises TypeError here
```

The exception escapes the Qt callback. Normally PyQt5 would `qFatal()`/abort, but the app
installs `styled_dialogs.install_qt_exception_guard()`, which **logs the exception and lets
the app keep running**. Result: the scheduled repaint still happens, the overlay renders
"Translating screen…", and `loading` is never cleared. Hang, forever, with no visible error.

Verified each link in that chain:
- `pyqtSignal(list).connect(@pyqtSlot(object))` → raises `TypeError` (standalone repro).
- Unguarded exception in a `singleShot` slot → process aborts with exit code 127 (standalone repro).
- `install_qt_exception_guard` (`styled_dialogs.py:15`) swallows it → app survives, overlay stuck.

### Why the test suite missed it
Every existing full-screen test mocks `_start_ocr`, so the real `connect()` never executed.

### The fix — `ocr.py`

1. `FullScreenOCRWorker.result_ready` is now `QtCore.pyqtSignal(object)`, with a comment
   explaining why it must not go back to `list`. `object` also keeps the
   `(x, y, w, h, text)` tuples intact instead of round-tripping them through `QVariant`.
2. Added `FullScreenTranslateOverlay._fail_translation(run_id, message_key)` — clears
   `loading`, sets a localized `error_message`, repaints.
3. `_restart_translation_from_controls()` wraps `_start_ocr()` in `try/except`, logs, and
   calls `_fail_translation(run_id, "ocr_init_failed")`. **A failure to start OCR can no
   longer present as an infinite spinner.**
4. `_on_ocr_complete()` wraps the translation-thread launch in `try/except` →
   `_fail_translation(run_id, "translation_failed")`; the no-text path now uses the same helper.
5. `_on_fullscreen_ocr_result()` falls back to `self.ocr_worker` when `self.sender()` is `None`.

### Verification
- End-to-end drive of the **real** `FullScreenTranslateOverlay` against the live desktop with
  a stubbed translator: overlay left the loading state in **0.35 s** and rendered
  **76 translated blocks**, `error_message is None`.
- Added 3 regression tests to `tests/test_ocr_overlay.py`:
  - `test_fullscreen_ocr_result_signal_connects_to_the_overlay_slot` (the real regression —
    connects the actual signal to the actual slot and asserts the tuple payload survives)
  - `test_fullscreen_start_ocr_failure_leaves_a_visible_error`
  - `test_fullscreen_ocr_without_text_stops_loading`
- Confirmed the new test **fails** on the pre-fix code with the exact `TypeError`, and
  **passes** after the fix. `tests/test_ocr_overlay.py`: 42 passed.

---

## 3. Issue #2 — Windows OCR language packs — IN PROGRESS

### 3.1 How the Windows mechanism actually works (measured, not guessed)

All of the below was **measured on this machine** (Windows 11 Pro, build 10.0.26100.7171) with two
elevated probe runs. Raw logs: `scratchpad/install_probe.log`, `install_probe2.log`,
`winrt_watch.log`, `winrt_watch2.log`.

**The model**
- Windows OCR languages are **Features on Demand (FODs)**, capability name
  `Language.OCR~~~<bcp47>~0.0.1.0` (e.g. `Language.OCR~~~fr-FR~0.0.1.0`).
- Microsoft documents that **`Language.OCR` depends on `Language.Basic~~~<same tag>~0.0.1.0`**.
  The app already installs Basic first — that is correct and must stay.
- Capability states are `NotPresent`, `Staged`, `Installed`, `Removed`.
- `app_version`-relevant: `windows_ocr_tag()` produces the right regional tags
  (`ru`→`ru-RU`, `zh`→`zh-CN`, `pt`→`pt-BR`, …). Verified against the live catalog. No bug there.

**Measured timings — this is the heart of the problem**

| Scenario | Capability | Time | Notes |
| --- | --- | --- | --- |
| `Staged` → `Installed` | `Language.Basic~~~es-ES` | **10.6 s** | payload already on disk |
| `Staged` → `Installed` | `Language.OCR~~~es-ES` | **5.2 s** | `Download Size: 0 bytes` |
| `NotPresent` → `Installed` | `Language.OCR~~~fr-FR` | **485 s (~8 min)** | real Windows Update download |

The 8-minute run's progress was extremely lumpy: 14.6 % for ~20 s, then **stuck on 35.4 % for
over four minutes** (t+25 s → t+279 s), then 76 % for another minute. `RestartNeeded = False`
in every case.

**What resolves immediately and what doesn't**
- `Get-WindowsCapability -Online -Name <cap>` reported `Installed` on **poll #0** in both probes,
  i.e. immediately after the servicing call returned. There is **no capability-state propagation
  lag** — the app's existing retry loop is guarding a problem that does not exist in that form.
- `OcrEngine.AvailableRecognizerLanguages` **does** pick up newly installed languages **without a
  process restart**: a long-lived Python process saw `es-ES` appear ~seconds after the install
  finished. (The second watcher reported "never" only because it timed out at 360 s while the
  French install needed 485 s — that run is inconclusive, not evidence of caching.) A fresh
  process afterwards lists `['en-US', 'es-ES', 'fr-FR', 'ru', 'zh-Hans-CN']` and
  `try_create_from_language('fr-FR')` succeeds.
- Not every app language has an OCR FOD on every build. On 26100 the catalog has **no
  `uk-UA` and no `hi-IN`**. The app already marks those "unavailable" correctly.
- `Get-WindowsCapability -Online | Where Name -like 'Language.OCR~~~*'` costs **1.2–3.5 s** per call.

### 3.2 Root causes of "unreliable / nothing happens"

**(a) No progress at all during the long download — the main cause.**
The installer script calls `Add-WindowsCapability`, which is a **blocking call that emits
nothing**. The script writes one `installing` status and then goes silent for up to ~8 minutes,
so the only thing moving in the UI is the elapsed clock. Users reasonably conclude it is hung.
The *remover* script already does the right thing: it runs `dism.exe` under `Start-Process` and
polls its stdout for a `NN%` token. The installer needs the same treatment.

**(b) Cancel is dead for minutes.** Because `Add-WindowsCapability` blocks, `Test-OcrCancel` is
only evaluated *after* it returns. Pressing Cancel appears to do nothing. The `dism.exe` +
poll-loop shape checks cancellation every 250 ms.

**(c) A successful install can be reported as a failure.**
`_install_windows_ocr_worker` probes WinRT **once**, with no retry:
```python
if not actual_tag or ocr._get_windows_ocr_engine(actual_tag) is None:
    unusable.append(code)
if unusable:
    raise RuntimeError("Windows installed the OCR capability but the recognition engine ...")
```
There is a short window where the capability is `Installed` but WinRT has not refreshed yet.
Hitting that window turns a *successful* install into a generic error message.

**(d) `_wait_for_windows_ocr_capabilities(attempts=12, delay=0.75)`** is bounded at roughly 23 s of
wall clock (each catalog query costs 1.2–3.5 s) and **emits no progress** while it runs.

### 3.3 What was changed — **DONE**

All in `settings_window.py`.

1. **New PowerShell helper `Install-OcrCapability`** inside `_windows_ocr_installer_script()`.
   It replaces both `Add-WindowsCapability` calls (Basic and OCR) with
   `dism.exe /Online /Add-Capability /NoRestart /English` launched via `Start-Process`, then
   polls the redirected stdout for `NN%` every 250 ms and republishes status each tick.
   Consequences: real progress, a live elapsed clock, and Cancel evaluated every 250 ms
   instead of once every several minutes.
   - Progress maths: each language occupies a slice of the overall bar, split into two slots
     (Basic = slot 0, OCR = slot 1): `overall = (100*index + (slot*100 + dismPercent)/2) / total`.
   - Exit codes: `0` and `3010` (success, restart requested) are both success. Any other code is
     only fatal if `Get-WindowsCapability` still does not report `Installed` — Windows sometimes
     returns a stale non-zero code after the work actually completed. This mirrors the logic the
     remover already had.
2. **`_wait_for_windows_ocr_capabilities(..., timeout=None)`** — now supports a wall-clock
   deadline (the worker passes 120 s), emits `win_registering` progress between polls, and
   still honours cancellation.
3. **New `_wait_for_windows_ocr_engines(codes, timeout=90, delay=2)`** — polls WinRT until it can
   actually build a recognizer, clearing `ocr._OCR_ENGINE_CACHE` / `ocr._UNIVERSAL_OCR_ENGINE`
   on each attempt. Returns the still-pending codes instead of raising.
4. **A lagging WinRT refresh is no longer an error.** If the capability is `Installed` but WinRT
   has not surfaced it before the deadline, the task now **succeeds** with the
   `win_installed_pending_restart` message telling the user to restart the app. Previously this
   produced a generic "Windows could not finish the OCR package operation" failure for an
   install that had in fact worked.
5. **Determinate progress bar.** `_emit_windows_ocr_status` now passes `determinate=True` for
   `installing`, `installing_basic` and `removing`, because those percentages come straight from
   dism.exe. (They were deliberately indeterminate before, when no real number existed.)
6. **New helper `_language_display_name(code)`** and two new localized keys in
   `WINDOWS_OCR_RUNTIME_TEXT` for all six interface languages: `win_registering`,
   `win_installed_pending_restart`.

**Background behaviour** was already correct and is unchanged: the progress dialog has a
"Continue in background" button, `OcrLanguageManagerDialog.reject()` refuses to kill a running
servicing task, and the elevated PowerShell runs in its own process tree so it survives even if
the app exits.

### 3.4 Verification
- Generated installer and remover scripts both parse cleanly via
  `[System.Management.Automation.Language.Parser]::ParseFile` (1683 / 884 tokens).
- **Live end-to-end run of the shipped installer script, start to finish** (elevated, Italian
  OCR, real Windows Update download path). The whole install took **989 s — 16.5 minutes** and
  the status stream reported continuous real progress the entire time:

  ```
  checking          0%    t+0s
  installing_basic  0 → 2 → 7 → 17 → 24 → 30 → 33 → 36 → 38 → 44 → 46 → 50%   t+2s … t+451s
  installing        50 → 52 → 57 → 67 → 74 → 80 → 83 → 88 → 94 → 96 → 100%    t+506s … t+989s
  ```

  The two-slot split works exactly as designed: `Language.Basic` fills 0–50 %, `Language.OCR`
  fills 50–100 %. Note the plateaus (t+29s→t+280s, t+539s→t+807s) — under the old
  `Add-WindowsCapability` code the dialog would have shown one frozen sentence for all
  16.5 minutes, which is precisely the "installation doesn't work / nothing happens" report.

  Final result: PowerShell **exit code 0**, `result.txt` = **`OK`**, **26 distinct status
  updates**, all five phases seen (`checking, installing_basic, installing, verifying, done`),
  and 23 monotonically increasing percentages `[0, 2, 7, 17, 24, 30, 33, 36, 38, 44, 46, 50, 50,
  52, 57, 67, 74, 80, 83, 88, 94, 96, 100]`.

  Afterwards: `Get-WindowsCapability … it-IT` → `Installed`; WinRT lists
  `['en-US', 'es-ES', 'fr-FR', 'it-IT', 'ru', 'zh-Hans-CN']`; and
  `ocr.installed_ocr_language_codes(engine="Windows")` → `['en', 'ru', 'fr', 'es', 'it', 'zh']`,
  so the app picks the new language up with no restart.

  (Side effect of testing: this machine now has Spanish, French and Italian Windows OCR
  installed that it did not have before. They can be removed from
  Settings → Language packages → Windows OCR if unwanted.)
- `tests/test_language_package_manager.py` + `tests/test_localization_completeness.py`: 47 passed.
- New tests added (see §6).

### 3.5 Relevant code
- `settings_window.py` `_windows_ocr_capability_catalog()` — `Get-WindowsCapability -Online`
  filtered to `Language.OCR~~~*`, 30 s timeout.
- `settings_window.py` `_windows_ocr_installer_script()` / `Install-OcrCapability`.
- `settings_window.py` `_install_windows_ocr_worker()`, `_wait_for_windows_ocr_capabilities()`,
  `_wait_for_windows_ocr_engines()`.
- `ocr.py` `_get_available_windows_ocr_language_tags()`, `_get_windows_ocr_engine()`,
  `_OCR_ENGINE_CACHE`, `_UNIVERSAL_OCR_ENGINE`.

---

## 4. Issue #3 — Update window redesign — **DONE**

The window is `launcher/ClicknTranslateApplyUpdate.cs` → `UpdateWindow : Form` (WinForms,
.NET Framework 4). It shows "Waiting for Click'n'Translate to close…", "Creating a safe
backup…", "Unpacking the portable update…", "Cleaning the backup…".

Why it looked bad: a stock `FormBorderStyle.FixedDialog` title bar (light, OS-drawn) over a dark
`#101114` client area, a stock `ProgressBar` in Marquee mode (Windows renders it with the system
theme and ignores the dark palette entirely), and a `FlatStyle.Flat` button that still draws a
system border. Nothing was owner-drawn, so it read as a raw WinForms dialog bolted onto the app.

### 4.1 What was changed

Everything is in `launcher/ClicknTranslateApplyUpdate.cs`. **No behaviour changed** — the update,
backup, verification and rollback logic is untouched; only presentation.

- **`Palette`** — the app's real tokens, lifted from `styled_dialogs.py`: background `#101114`,
  title bar `#151515`, hairline `#29292d`, border `#33313c`, text `#f5f5f7`, muted `#b8b8c2`,
  accent `#7959a0` / `#a985d2` / `#c5b3e9`, track `#211f28`, danger `#c42b1c` / `#d94a4a`.
- **`AccentProgressBar`** — replaces the stock `ProgressBar`. Owner-drawn, double-buffered,
  rounded track, purple gradient. Indeterminate mode animates a soft gradient sweep at 30 fps;
  determinate mode fills left-to-right. Turns red on failure.
- **`AccentButton`** — owner-drawn rounded button using the accent border, with hover state and a
  properly dimmed disabled look.
- **`CaptionButton`** — minimise / close glyphs for the custom title bar; close goes red on hover
  exactly like `StyledMessageBox`.
- **Frameless window** with a custom `#151515` title bar carrying the app icon and caption.
  Dragging is handed to Windows via `ReleaseCapture` + `WM_NCLBUTTONDOWN`/`HTCAPTION` so snapping
  and multi-monitor behaviour stay native. Rounded corners via
  `DwmSetWindowAttribute(DWMWA_WINDOW_CORNER_PREFERENCE=33, DWMWCP_ROUND=2)`, silently ignored
  before Windows 11. A 1px `#33313c` border is drawn in `OnPaint`.
- **DPI correctness.** The manifest declares PerMonitorV2, and .NET Framework WinForms does *not*
  rescale for that, so the first attempt clipped the title's descenders on a 150 % display. Layout
  now uses a `TableLayoutPanel` with `AutoSize` labels (`MaximumSize` for wrapping) and every fixed
  dimension goes through `S(int)`, which scales by `Graphics.FromHwnd(IntPtr.Zero).DpiX / 96`.
  Verified visually at 150 %: no clipping, correct rhythm.

### 4.2 Build path

Must stay .NET Framework / WinForms — compiled with `csc.exe`, no WPF, no NuGet, and **no C# 6+
syntax** (this compiler is C# 5).
- `tools/build_launcher.ps1` → `launcher/ClicknTranslateLauncher.cs` + `SilentWinFormsDialog.cs`
- `tools/build_update_bootstrap.ps1` → `launcher/ClicknTranslateUpdateBootstrap.cs`
- `tools/build_update_repair.ps1` → `launcher/ClicknTranslateUpdateRepair.cs`
- **`tools/build_apply_updater.ps1` → `launcher/ClicknTranslateApplyUpdate.cs` (NEW — see §5)**
- Compiler: `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`

---

## 5. Blocker found and fixed: the release script could not run

`tools/stage_release.ps1` line 54 calls `tools/build_apply_updater.ps1` to produce
`app\_internal\ClicknTranslateUpdater.exe`, and then *asserts that file exists* in its `$required`
list. **That script did not exist in the repo.** Any attempt to stage a release would have failed
outright. Created:

- `tools/build_apply_updater.ps1` — modelled on `build_update_repair.ps1`; compiles
  `ClicknTranslateApplyUpdate.cs` + `SilentWinFormsDialog.cs` with the `System.IO.Compression*`
  references the zip path needs.
- `launcher/ClicknTranslateApplyUpdate.manifest` — `asInvoker` (the app elevates the helper itself
  in `settings_window._launch_apply_updater`, so `requireAdministrator` here would add a second,
  pointless UAC prompt for portable installs), PerMonitorV2, longPathAware.

Verified: the helper compiles and runs.

---

## 6. Files changed

| File | Change |
| --- | --- |
| `ocr.py` | Full-screen translate fix: `pyqtSignal(object)`, `_fail_translation()`, start guards |
| `settings_window.py` | dism-based OCR install with real progress; deadline waits; WinRT-lag tolerance; 2 new localized keys ×6 languages; `_language_display_name()` |
| `launcher/ClicknTranslateApplyUpdate.cs` | Full visual redesign (palette, owner-drawn progress/buttons, frameless chrome, DPI scaling) |
| `launcher/ClicknTranslateApplyUpdate.manifest` | **new** — manifest for the update helper |
| `tools/build_apply_updater.ps1` | **new** — the missing build script `stage_release.ps1` requires |
| `tests/test_ocr_overlay.py` | +3 regression tests for the full-screen path |
| `tests/test_language_package_manager.py` | Updated install-script assertions; +4 tests |
| `tests/test_version_consistency.py` | Also assert the two new files carry the release version |
| `.gitignore` | `!tools/*.ps1` (see §9b) and `.venv*/` |
| `HANDOFF.md` | This file (new) |

### Tests added
- `test_fullscreen_ocr_result_signal_connects_to_the_overlay_slot` — the actual regression;
  fails on the pre-fix code with the exact `TypeError`.
- `test_fullscreen_start_ocr_failure_leaves_a_visible_error`
- `test_fullscreen_ocr_without_text_stops_loading`
- `test_windows_installer_treats_restart_exit_code_as_success`
- `test_windows_install_reports_success_when_winrt_lags_behind`
- `test_wait_for_windows_ocr_engines_gives_up_without_raising`
- `test_wait_for_windows_ocr_engines_clears_stale_engine_cache`
- `test_windows_install_status_never_presents_a_fake_percentage` → renamed to
  `..._shows_real_dism_progress_and_elapsed_time` (behaviour intentionally changed).

## 7. Scratch/debug artifacts (outside the repo, safe to delete)

`C:\Temp\claude\D--1python-projects-clickntranslate-main\db7a27df-18aa-4e17-a1bf-26a9050d79da\scratchpad\`
- `repro_fullscreen.py` — times the whole WinRT full-screen OCR pipeline on the live desktop
- `repro_signal.py` — minimal proof of the `pyqtSignal(list)` / `pyqtSlot(object)` mismatch
- `repro_slot_exception.py` — shows an unguarded slot exception aborts PyQt (exit 127)
- `verify_fullscreen.py` — drives the real overlay end-to-end with a stubbed translator
- `install_probe.ps1` / `install_probe2.ps1` + `.log` — the elevated FOD timing probes
- `winrt_watch.py` + `winrt_watch*.log` — WinRT language visibility watchers
- `e2e_install.py` — runs the shipped installer script elevated and tails `status.json`
- `preview_update_window.ps1`, `update_window_1.png` — sandboxed preview + screenshot of the
  redesigned window (creates a fake install tree in temp; never touches a real installation)

## 8. Status of the engineering work (all done)

- [x] Issue #1 — full-screen translation fixed and verified end to end.
- [x] Issue #2 — OCR language install: real progress, responsive cancel, tolerant verification.
      Validated by a full 989 s live install (§3.4).
- [x] Issue #3 — update window redesigned, DPI-correct, visually verified at 150 % scaling.
- [x] Release blocker: created the missing `tools/build_apply_updater.ps1` (§5).
- [x] `.gitignore` root cause fixed (§9b).
- [x] Full test suite: **286 passed, 8 subtests passed** (`.venv`, Python 3.13).
- [x] `py_compile` clean on `ocr.py`, `settings_window.py`, `main.py`, `translater.py`.

*(The 1.5.3 build/staging figures that used to live here are superseded by the 1.5.4
release record in §11. Inno Setup, previously missing, was installed — see §11.1.)*

## 9. Build environment constraint — **the release must not be built on Python 3.13**

`requirements.txt` pins `rapidocr-onnxruntime==1.4.4`, and that wheel declares
`Requires-Python >=3.6,<3.13`. On Python 3.13 pip resolves no further than 1.2.3 and
`pip install -r requirements.txt` **fails outright**:

```
ERROR: Could not find a version that satisfies the requirement rapidocr-onnxruntime==1.4.4
```

`ClicknTranslate.spec` bundles RapidOCR into the OCR worker, so this is not optional for a
release build. Use **Python 3.11** (present on this machine at
`C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe`) or any 3.12.

Note the two virtualenvs in the tree:
- `.venv` — Python 3.13, used for running the test suite (286 passed).
- `.venv311` — Python 3.11, created for the release build.

`tools/stage_release.ps1` hardcodes `.venv\Scripts\python.exe` for its PyInstaller step, so
either point `.venv` at 3.11 before a real release, or run PyInstaller manually with `.venv311`
and then call `stage_release.ps1 -SkipPyInstaller`.

## 9b. `.gitignore` fixed — this is how the build script went missing

`.gitignore` ignores `*.ps1` wholesale and then whitelisted exactly four scripts by name.
`tools/build_apply_updater.ps1`, `tools/build_update_bootstrap.ps1` and
`tools/build_network_setup.ps1` were **not** on that list, so they could never be committed —
which is almost certainly why `build_apply_updater.ps1` was absent from the repo while
`stage_release.ps1` still required it. Replaced the four name-by-name exceptions with
`!tools/*.ps1`, and added `.venv*/` to the virtualenv rule.

## 10. Release procedure — the exact sequence that produced 1.5.4

Run every step from `D:\1python_projects\clickntranslate-main`. Order matters where noted.

```powershell
# 0. Bump the version everywhere first (see §11.3 for the full file list), then:

# 1. PyInstaller MUST run on Python <= 3.12 (see §9). app_version.py is baked in here,
#    so always rebuild after a version bump.
.\.venv311\Scripts\python.exe -m PyInstaller ClicknTranslate.spec --clean --noconfirm

# 2. Stage: copies dist, builds the launcher and the apply-update helper.
.\tools\stage_release.ps1 -Version 1.5.4 -SkipPyInstaller

# 3. Portable zip. Must include the base directory: the published zips all have a
#    top-level ClicknTranslate\ folder (verified against 1.5.3 with an HTTP range request).
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  (Resolve-Path 'releases\ClicknTranslate-v1.5.4-win64-stage\ClicknTranslate'),
  (Join-Path (Get-Location) 'releases\Click-n-Translate-1.5.4-windows-portable-x64.zip'),
  [System.IO.Compression.CompressionLevel]::Optimal, $true)

# 4. Inno Setup installer (~2.7 min at lzma2/ultra64).
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer\ClicknTranslate.iss

# 5. RENAME BEFORE STEP 6. Inno writes ClicknTranslate-Setup-v<ver>-win64.exe, which is
#    exactly the filename the network setup wants to write in step 6. Renaming first is
#    what frees the name; skipping this silently overwrites the 126 MB installer with the
#    90 KB downloader.
Move-Item releases\ClicknTranslate-Setup-v1.5.4-win64.exe `
          releases\Click-n-Translate-1.5.4-windows-x64-installer.exe

# 6. Network setup: a ~90 KB downloader that pulls the full installer. It embeds the
#    installer's final download URL and SHA-256, so compute the hash after step 5.
#    The URL is deterministic, so this does not require uploading first.
.\tools\build_network_setup.ps1 -Version 1.5.4 `
  -SetupUrl 'https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.5.4/Click-n-Translate-1.5.4-windows-x64-installer.exe' `
  -SetupSha256 '<sha256 of the renamed installer>'

# 7. Commit + tag from a clone (see §11.2), then publish as a DRAFT first,
#    verify the assets, and only then flip it live.
gh release create v1.5.4 --repo jabrailkhalil/clickntranslate `
  --title "Click'n'Translate 1.5.4" --notes-file notes.md --draft `
  releases\Click-n-Translate-1.5.4-windows-x64-installer.exe `
  releases\Click-n-Translate-1.5.4-windows-portable-x64.zip `
  releases\ClicknTranslate-Setup-v1.5.4-win64.exe
gh release edit v1.5.4 --repo jabrailkhalil/clickntranslate --draft=false --latest
```

Notes:
- `tools/build_update_repair.ps1` embeds `-PackageUrl` and `-PackageSha256`. **Update the SHA to
  the new portable zip's digest on every release** or the repair tool will refuse the download.
  `tests/test_update_repair.py` enforces that the placeholder is gone and the digest is 64 hex
  characters, so a forgotten update fails the suite rather than shipping silently.
- `tools/build_update_bootstrap.ps1` was **not** used for 1.5.4; no bootstrap zip has been
  attached to a release since 1.5.2, and the updater explicitly skips assets containing
  "bootstrap".

---

## 11. The 1.5.4 release record

### 11.1 Toolchain change made on this machine

**Inno Setup 6.7.3 was installed** via `winget install --id JRSoftware.InnoSetup`. winget ran
unelevated, so it landed **per-user**:

```
C:\Users\admin\AppData\Local\Programs\Inno Setup 6\ISCC.exe
```

Not in `Program Files` — scripts that probe only `%ProgramFiles%`/`%ProgramFiles(x86)%` will not
find it. This is what previously blocked building the installer asset.

### 11.2 Git — how the commit was actually made

The working directory is **not** a git repository, so committing directly was impossible.
Procedure used:

1. `git clone https://github.com/jabrailkhalil/clickntranslate.git` into the scratchpad
   (`<scratchpad>\cnt-remote`).
2. Compared both trees. **82 files looked different, but 57 of those were line endings only** —
   the working directory is LF, the git checkout is CRLF because `core.autocrlf=true` globally.
   After newline normalization the real diff was exactly **28 files** (25 modified + 3 new),
   matching the edits made. No unexpected divergence from `main`.
3. Copied those 28 files into the clone, `git add -A`, committed, pushed `main`, tagged, pushed
   the tag.

Result:
- commit **`c84a010`** — "Fix full-screen translation and Windows OCR installs, release 1.5.4"
  (28 files changed, 1567 insertions, 156 deletions), pushed to `main` (`9d0ff13..c84a010`).
- annotated tag **`v1.5.4`** → `c84a010`, pushed.

If you repeat this, remember the clone is the source of truth for git; the working directory has
no `.git`.

### 11.3 Files touched by the version bump (1.5.3 → 1.5.4)

`app_version.py`, `installer/ClicknTranslate.iss`,
`installer/windows/ClicknTranslate.exe.manifest`, and the three launcher manifests
(`ClicknTranslateApplyUpdate`, `ClicknTranslateUpdateBootstrap`, `ClicknTranslateUpdateRepair`),
all seven `tools/*.ps1` version defaults, `README.md` + the four `docs/readme/README.*.md`, and
the version assertions in `tests/test_version_consistency.py`, `tests/test_updater.py`,
`tests/test_update_repair.py`.

`tests/test_version_consistency.py` is the guard — it asserts the exact version string in every
one of those files, so a missed spot fails the suite.

**Deliberately left at their historical versions:** `store/microsoft-store/*` documents the 1.5.0
Microsoft Store submission and certification run; it is a record of that event, not a value that
tracks the current release. `tools/test_update_152_to_153_e2e.py` is a manual harness for the
1.5.2→1.5.3 upgrade path and is not collected by pytest (`pytest.ini` sets `testpaths = tests`).

### 11.4 Released artifacts

| Asset | Size | SHA-256 |
| --- | --- | --- |
| `Click-n-Translate-1.5.4-windows-x64-installer.exe` | 132,567,117 (126.4 MB) | `D87CD7C5983E9676033A98D511761FB4452DEAC209703F61CD796AE7F3263B53` |
| `Click-n-Translate-1.5.4-windows-portable-x64.zip` | 211,060,766 (201.3 MB) | `0301C383576B091DE94176269FF9178BFE19CB4419C63EE16A5F26BAB5D90432` |
| `ClicknTranslate-Setup-v1.5.4-win64.exe` | 89,600 | (network downloader) |

The three names match v1.5.3's asset set exactly, which matters: `SettingsWindow._pick_update_asset`
scores asset names to decide what an installed copy vs a portable copy downloads.

Staged package contents (all verified present by `stage_release.ps1`'s own `$required` check):

```
ClicknTranslate.exe                              87,040  v1.5.4.0
app\ClicknTranslateApp.exe                   11,255,439
app\_internal\ArgosWorker.exe                 9,951,334
app\_internal\OcrWorker.exe                   7,778,907
app\_internal\ClicknTranslateUpdater.exe        104,960  v1.5.4.0
```

### 11.5 Extra fix folded into this release

`tools/build_update_repair.ps1` defaulted to
`.../releases/download/v<ver>/ClicknTranslate-v<ver>-win64.zip`. **No release has ever published
an asset with that name**, so the repair tool would have downloaded a 404. It now points at
`Click-n-Translate-<ver>-windows-portable-x64.zip` with that file's real digest, and both
`tests/test_version_consistency.py` and `tests/test_update_repair.py` were updated to enforce the
corrected convention.

### 11.6 Post-publish verification (all green)

The release was created as a **draft**, verified, and only then flipped live — so it was never
visible to the in-app updater in a half-uploaded state.

1. **Asset integrity.** GitHub's reported `digest` for each uploaded asset was compared against the
   locally computed SHA-256. Both large assets matched byte-for-byte; all three report
   `state=uploaded` with the exact expected byte counts.
2. **Release state.** `tag=v1.5.4  draft=false  target=main`, marked **Latest**, published
   2026-08-05T07:15:22Z.
3. **Public URLs resolve.** HTTP range requests returned `206` with the correct total size for:
   - `…/releases/latest/download/Click-n-Translate-1.5.4-windows-x64-installer.exe` → 132,567,117
   - `…/releases/latest/download/Click-n-Translate-1.5.4-windows-portable-x64.zip` → 211,060,766
   - `…/releases/download/v1.5.4/Click-n-Translate-1.5.4-windows-x64-installer.exe` → 132,567,117
     (this exact URL is compiled into the network setup)
   - `…/releases/download/v1.5.4/ClicknTranslate-Setup-v1.5.4-win64.exe` → 89,600

   The first two are the links the READMEs use, so the download buttons work.
4. **The real updater logic was run against the live release JSON.**
   `SettingsWindow._pick_update_asset` on the actual published payload selects:
   - installed copy → `Click-n-Translate-1.5.4-windows-x64-installer.exe`
   - portable copy → `Click-n-Translate-1.5.4-windows-portable-x64.zip`

   So existing 1.5.x users get the correct artifact for their install type.

Release URL: <https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.5.4>

---

## 11b. 1.5.4 shipped broken — three defects and their root causes

After 1.5.4 went out, three problems were reported against the installed build at
`D:\Soft\workstation\ClicknTranslate`. **Two were caused by how 1.5.4 was built, not by the
source changes.** Both are build-environment traps that are now guarded against in the spec.

### (a) ArgosWorker.exe crashed instantly — 0xC0000005

Symptom: "Could not load package list: Argos offline worker failed: exit code 3221225477" and
Argos offline translation dead. Reproduced by running the worker directly: instant segfault, no
stderr at all, i.e. a native crash before Python could report anything.

Windows Error Reporting named the faulting module:

```
Faulting module name: MSVCP140.dll, version: 14.27.29016.0
Exception code: 0xc0000005
```

The bundle contained a **mismatched Visual C++ runtime**:

| DLL | shipped version |
| --- | --- |
| MSVCP140.dll | 14.27.29016.0 |
| MSVCP140_1.dll | 14.51.36247.0 |
| VCRUNTIME140.dll | 14.38.33126.1 |

`MSVCP140_1.dll` is an extension of `MSVCP140.dll`; the two must come from the same
redistributable. Cause: **PyInstaller resolves DLL dependencies using the Windows search order,
which includes `PATH`.** This build machine has
`C:\Program Files\AdoptOpenJDK\jdk-17.0.0.20-hotspot\bin` on PATH, and it ships its own
`MSVCP140.dll` 14.27 — which won over System32's 14.51. `MSVCP140_1.dll` is not in the JDK
folder, so that one still came from System32. Result: a runtime pair that cannot work together.

Proven by copying System32's consistent 14.51 set over the build output: the worker went from
instant segfault to `exit 0` returning the full Argos package catalog.

**Fix:** `ClicknTranslate.spec` now rewrites every `msvcp140*/vcruntime140*/concrt140` entry to
the System32 copy (`_pin_system_vcruntime`), and `_assert_consistent_vcruntime` fails the build
outright if more than one runtime version is still collected.

### (b) EasyOCR / RapidOCR installs failed — wrong build Python

Symptom: `ERROR: Could not find a version that satisfies the requirement scipy==1.18.0
(from versions: … 1.17.1)`, with pip downloading **cp311** wheels.

`settings_window._find_rapidocr_install_python_command` deliberately looks for a system Python
matching **the frozen app's own version**, because those wheels get imported by the frozen
`OcrWorker`, so the ABI must match. 1.5.4 was built on **Python 3.11**, so it went looking for
3.11 — but `EASYOCR_PIP_PACKAGES` pins `scipy==1.18.0` and `numpy==2.5.1`, which require
Python >= 3.12, and the embedded fallback interpreter is `EASYOCR_PYTHON_VERSION = "3.12.10"`.

So the whole engine-install mechanism is designed around **Python 3.12**, and building on 3.11
broke it. (3.11 was chosen only because `rapidocr-onnxruntime==1.4.4` requires < 3.13 — but 3.12
satisfies that too and is the correct choice.)

**Fix:** the spec now reads `EASYOCR_PYTHON_VERSION` out of `settings_window.py` and **refuses to
build** unless the build interpreter is that same series. `.venv312` is the build environment
from now on; `.venv311` should be considered dead.

### (c) Tesseract language install failed, then worked on retry

`ocr._prepare_tesseract_data` downloaded each `*.traineddata` with a single `requests.get`
against `github.com/tesseract-ocr/tessdata` — tens of megabytes with **no retry**, so any
transient drop failed the whole install. That is exactly the reported "failed, tried again, it
worked".

**Fix:** bounded retry (`_TESSDATA_DOWNLOAD_ATTEMPTS = 3`) with linear backoff, treating a
truncated transfer as retryable, cancellation still honoured, plus a localized `tess_retrying`
status in all six languages. Covered by two new tests.

### (d) Tooltips (this one was a genuine UI issue, not a build problem)

The same `QToolTip` block was pasted into four different stylesheets, so any widget outside those
four fell back to the system tooltip. There were no rounded corners, and long tooltips ran off
the screen because **Qt only word-wraps a tooltip when the text looks like rich text**
(`QTipLabel` does `setWordWrap(Qt::mightBeRichText(text))`).

**Fix:** one shared `TOOLTIP_QSS` in `styled_dialogs.py` (now with `border-radius`), applied
app-wide via `install_tooltip_style()` so unstyled windows match too, plus `tooltip_text()`,
which wraps anything longer than 44 characters into a fixed 320px block and leaves short labels
compact. Applied at all 45 `setToolTip` call sites.

### 11c. The 1.5.5 release

Built on **Python 3.12.10** in `.venv312` (the spec now enforces this). Same procedure as §10,
with the version strings bumped to 1.5.5.

Verification specific to the 1.5.4 defects:

- **VC runtime is now one consistent set** in the shipped bundle:
  `MSVCP140.dll`, `MSVCP140_1.dll`, `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll` all
  **14.51.36247.0** (1.5.4 shipped 14.27 / 14.51 / 14.38 / 14.38).
- **`ArgosWorker.exe` runs**: exit 0, returns the full **100-package** Argos catalog. Previously
  an instant segfault.
- **Frozen interpreter is `python312.dll`** (1.5.4 shipped `python311.dll`).
- **All 26 `EASYOCR_PIP_PACKAGES` pins resolve** under 3.12 via `pip install --dry-run --report`,
  including the `scipy==1.18.0` that could not resolve on 3.11.
- Full suite: **289 passed** (up from 286; +3 new tests for the Tesseract retry and tooltips).

Artifacts:

| Asset | Size | SHA-256 |
| --- | --- | --- |
| `Click-n-Translate-1.5.5-windows-x64-installer.exe` | 125.2 MB | `8B1C51AC978438D85DF20A3A8DF2C0A0E3468395FF1DB7EBD445E87407558D0C` |
| `Click-n-Translate-1.5.5-windows-portable-x64.zip` | 198.0 MB | `8745500C5CE076D25133083EDAA286629F22998DCE8FFB508B8704AED4DD00AA` |
| `ClicknTranslate-Setup-v1.5.5-win64.exe` | 89,600 B | network downloader |

Git: commit **`1980bf3`** on `main`, annotated tag **`v1.5.5`**.

---

## 12. If you are picking this up next

**State right now:** 1.5.4 is fully released. `main` is at `c84a010`, tag `v1.5.4` points at it,
and all three assets are published and verified. Nothing is half-finished.

Things that will bite you if you do not know them:

1. **The working directory has no `.git`.** Commit from a clone (§11.2). The two trees differ only
   by line endings (LF locally, CRLF in a checkout with `core.autocrlf=true`) — a naive byte diff
   reports ~57 false positives, so always normalize newlines before comparing.
2. **Build releases with Python 3.12 only — use `.venv312`.** Not 3.13 (`rapidocr-onnxruntime`
   will not resolve) and not 3.11 (the runtime OCR engine installs break, §11b(b)). The spec now
   enforces this by reading `EASYOCR_PYTHON_VERSION`, so a wrong interpreter fails the build
   instead of shipping. `.venv` (3.13) is for running tests only; `.venv311` is dead — delete it.
2b. **Do not trust the build machine's PATH.** The spec pins the VC runtime to System32 and
   asserts a single version, because a stray `MSVCP140.dll` on PATH silently broke 1.5.4
   (§11b(a)). If that assertion ever fires, do not work around it — find the stray DLL.
3. **Rename the Inno output before building the network setup** (§10, step 5) or you will overwrite
   a 126 MB installer with a 90 KB downloader that has the same filename.
4. **`tools/build_update_repair.ps1` carries a pinned SHA-256** of the portable zip. It must be
   recomputed every release. The test suite catches a stale placeholder but cannot catch a digest
   that is merely wrong, so update it whenever the zip is rebuilt.
5. **Inno Setup is installed per-user** at `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`, not in
   Program Files (§11.1).
6. **Publish as a draft first**, verify assets, then `gh release edit --draft=false --latest`.
   Publishing immediately pushes the build to every existing user through the in-app updater.

Worth doing but not required:
- `git init` the working directory and wire up the remote, to remove trap #1 permanently.
- Consider a `.gitattributes` with `* text=auto` so line endings stop being a source of noise.
- `tools/test_update_152_to_153_e2e.py` is now two releases stale; if the upgrade path is still
  worth exercising, it needs porting to 1.5.3 → 1.5.4.

Side effect of the OCR investigation: this machine gained Spanish, French and Italian Windows OCR
languages. Remove them from Settings → Language packages → Windows OCR if unwanted.

---

## 13. The Linux port (in progress)

Started after 1.5.5. **Windows behaviour is unchanged** — every Windows path still runs the same
code, and the Windows suite stays green (344 passed, 10 skipped; the skips are the AF_UNIX socket
tests, which only apply to Linux).

### 13.1 Design decisions and why

These follow what the closest comparable Linux apps do, not invention:

| Decision | Rationale |
| --- | --- |
| **No in-app global hotkeys.** The user binds `clickntranslate --ocr` etc. in their desktop settings | X11 grabs collide with the desktop and Wayland forbids them. NormCap has an ADR for exactly this; Flameshot asks users to bind `flameshot gui` |
| **Capture via xdg-desktop-portal on Wayland**, Qt on X11, with `grim`/`gnome-screenshot`/`spectacle` fallbacks | Flameshot ≥12 and NormCap both use the portal; the helpers cover compositors whose portal is missing |
| **AppImage + tarball**, Flatpak deferred | NormCap now prefers Flatpak, but it has no runtime-installed engines. Ours pip-installs EasyOCR/RapidOCR through a *system* Python and downloads Argos models — a Flatpak sandbox breaks both |
| **No self-update**, only a version check | The updater is C#/WinForms + Inno + exe replacement. Linux packages are updated by whatever installed them |

### 13.2 New modules

* `platform_support.py` — the only place that asks which OS this is. XDG dirs, executable
  suffixes, `no_window_kwargs()` (the STARTUPINFO/CREATE_NO_WINDOW pair), which OCR engines
  exist, `supports_in_app_update()`.
* `single_instance.py` — AF_UNIX socket in `$XDG_RUNTIME_DIR`, `0600`. Second launches send a
  command and exit; the running instance dispatches it through the existing hotkey dispatcher,
  so the UI thread handling is identical to Windows. Reclaims a socket left by a crash.
* `linux_capture.py` — portal → helper → clear error, and crops a whole-desktop grab to the
  requested screen.
* `linux_desktop.py` — `.desktop` entries (with right-click actions for the capture commands),
  hicolor icon install, autostart in `~/.config/autostart`.
* `ClicknTranslate-linux.spec`, `requirements-linux.txt`, `tools/setup_linux_env.sh`,
  `tools/build_linux_release.sh`, `docs/LINUX.md`.

`ocr.py` gained `grab_screen_pixmap()`; all four `grabWindow` call sites now go through it.

### 13.2b Behaviour fixes that also apply to Windows

Porting surfaced three defects that were not Linux-specific. All three are covered by tests:

1. **Tesseract languages now come from `tesseract --list-langs`**, with the old directory scan
   kept as a fallback. The scan only looked next to the binary, which is right for the portable
   Windows install but finds nothing for a distribution package
   (`/usr/share/tesseract-ocr/4.00/tessdata`).
2. **`ocr.usable_ocr_engine()`** maps a configured engine that does not exist on this platform
   onto the platform default, and logs it. Without it a `config.json` written on Windows sent
   the Linux app down the WinRT path and it reported a missing engine.
3. **A saved OCR language that is not installed no longer leaves the selector unselected.**
   The overlay fell through to a modal "install a language pack" dialog with `currentData()`
   returning `None`; it now falls back to the first installed language. This is also what made
   the headless test run hang — a modal dialog with nobody to click it.

### 13.3 Verified in Ubuntu 22.04 (WSL2, headless)

* **The packaged `ArgosWorker` translates offline** — ru→en returned "Hello, world! How are you
  today?" with no torch and no onnxruntime in the bundle. The stanza/minisbd stubs and the
  in-house sentence splitter are platform-independent, so the 1.5.x Argos fix ports as is.
* The PyInstaller Linux build produces all three executables (465 MB onedir).
* The GUI binary starts, writes its portable `data/config.json` next to the binary, and creates
  the command socket.
* A second launch with `--ocr` / `--translate` delivers the command and exits 0 while the first
  instance keeps running.
* Tesseract 4.1.1 is found on `PATH`, and `--list-langs` reports `eng`/`osd`/`rus`, which the
  app maps to `en`/`ru`.
* **The full test suite passes on both systems**: Linux 370 passed / 29 skipped, Windows 388
  passed / 11 skipped. The skips are the mechanism that does not exist on that system (AF_UNIX
  sockets and the XDG entries on Windows; the Windows OCR tab, Startup shortcut, MSIX layout and
  UAC elevation on Linux).

### 13.3b Artifacts

`tools/build_linux_release.sh` produces both, and both were built and smoke-tested:

| Artifact | Size |
| --- | --- |
| `Click-n-Translate-1.5.5-linux-x86_64.AppImage` | 157 MB |
| `Click-n-Translate-1.5.5-linux-x86_64.tar.gz` | 156 MB |

The AppImage starts, keeps its data in `~/.local/share/clickntranslate` (its own mount is
read-only, which `portable_paths._linux_portable_base_dir` detects), and answers shortcut
commands. The tarball keeps the Windows-style portable layout: data sits next to the binary.

Updates are check-only off Windows: `check_for_updates` announces the version and opens the
release page rather than replacing the running app, because the C#/WinForms updater helpers do
not exist here.

### 13.3c Desktop details handled after the first commit

The first pass made the app build and run; these are the platform behaviours that decide
whether it is actually usable on a Linux desktop:

* **No tray, no disappearing app.** `QSystemTrayIcon.isSystemTrayAvailable()` is false on GNOME
  without the AppIndicator extension and on plenty of window managers. Minimizing now goes to
  the taskbar and closing exits, instead of hiding the window into a tray that does not exist.
* **Clipboard ownership.** X11/Wayland keep the clipboard inside the process that set it, and
  the capture overlay is a short-lived subprocess, so copied text used to depend on a clipboard
  manager being installed. `platform_support.copy_text()` hands the text to `wl-copy`/`xclip`/
  `xsel` in a detached process; every `pyperclip.copy` call site now goes through it (on Windows
  it still ends up in pyperclip, unchanged).
* **Selection translation** reads the PRIMARY selection instead of simulating Ctrl+C, so it
  needs no key injection and does not overwrite the clipboard.
* **Hy-MT** keeps working from a user-supplied llama.cpp runner (`hymt`, `llama-cli`,
  `llama-run`, `main` — no `.exe`), but the automatic download stays Windows-only: the pinned
  archive and its SHA-256 are the Windows x64 build, and shipping an unverified Linux binary
  instead would be worse than explaining where to put one.
* **EasyOCR/RapidOCR** need an interpreter matching the frozen build's version, so the installer
  now probes `python3.<minor>` before the generic `python3` (distributions ship versioned
  binaries) and, when it finds nothing, names the package to install instead of falling back to
  the Windows embedded-Python bootstrap.
* **High-DPI and the launcher icon.** The exe manifest that gives Windows per-monitor DPI
  awareness has no Linux equivalent, so Qt scaling is enabled explicitly before the
  QApplication exists, `setDesktopFileName` ties the window to its `.desktop` entry, and the
  entry is installed on first run and rewritten whenever the executable moves (a new AppImage).

### 13.3d Two things the headless verification got wrong at first

Worth knowing, because both made a broken check look green:

1. **The first run blocks on a modal dialog.** `DarkThemeApp.__init__` shows `WelcomeDialog`
   with `exec_()` when `show_update_info` is true, so a headless run sits there forever with
   nobody to click it. The IPC thread keeps answering commands from that state, so
   `clickntranslate --ocr` returned 0 while nothing happened behind it — the socket replied,
   but `_main_window_ref` was still None. Verify past the first run by seeding
   `show_update_info: false`, which is the state the app spends its life in.
   The desktop entry install was moved ahead of the window for the same reason.
2. **Widgets were being created off the GUI thread.** The startup warm-up thread called
   `prepare_overlay()` for all three modes, which constructs QWidgets. Windows tolerates it;
   X11 printed `QBasicTimer::start: QBasicTimer can only be used with threads started with
   QThread` and would eventually misbehave. On Linux the creation now hops back to the GUI
   thread through the same dispatcher the shortcut commands use. Windows keeps its shipped
   behaviour.

### 13.4 Not verified — needs a real desktop session

Screen capture on X11 and Wayland, the selection overlay, the tray icon, and the desktop
shortcut bindings. WSL2 on Windows 10 has no WSLg, so there is no display to test against.
The Wayland portal path in particular is written against the spec and reviewed, not run.

### 13.5 Build environment note

`.venv312` is required for **Windows** releases (`EASYOCR_PYTHON_VERSION`). The Linux spec does
not enforce a version yet — the WSL environment is Python 3.10. Before shipping a Linux build
that must support runtime EasyOCR/RapidOCR installs, decide which interpreter the Linux engine
installer targets and add the same guard to `ClicknTranslate-linux.spec`.
