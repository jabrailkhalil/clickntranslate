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
* **The full test suite passes on both systems**: Linux 375 passed / 29 skipped, Windows 393
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

### 13.3e Functional sweep — `tools/functional_check.py`

A new harness drives every feature against the real thing (live providers, the installed
Tesseract, the Argos model, the command socket, the clipboard, the desktop files, the packaged
workers) and prints a pass/fail matrix. Skips mean "not present on this machine", never
"not checked".

    python tools/functional_check.py --frozen dist/clickntranslate

Results: **Linux 51 passed / 0 failed / 7 skipped**, **Windows 34 passed / 0 failed / 6 skipped**.

It immediately found a blocking Linux bug the unit suite could not:

**Tesseract — the default Linux engine — could not run at all.**
`_configure_installed_tesseract_data()` only looked for tessdata beside the binary
(`/usr/bin/tessdata`, `/usr/tessdata`), which is correct for the portable Windows install and
finds nothing for a distribution package (`/usr/share/tesseract-ocr/4.00/tessdata` on Debian).
It returned "", and `_recognize_tesseract_variants_with_cmd` treats that as "language data not
installed" and refuses to run — so OCR silently produced nothing while the `tesseract` CLI read
the same image perfectly. Fixed by scanning the standard system locations and, failing that,
trusting a binary whose `--list-langs` already reports the language. Five regression tests in
`tests/test_platform_ocr_gating.py`.

Also closed: **RapidOCR is now bundled into the Linux OcrWorker** (`requirements-linux.txt` pins
`rapidocr-onnxruntime==1.4.4`), matching Windows, where it works on first launch without a
runtime install. Verified by sending a real image to the packaged worker and comparing the text.
The build grows to ~700 MB unpacked, 255 MB as an AppImage.

### 13.3f A build that exited 0 and produced an unusable exe

Reported symptom: `dist\ClicknTranslate\ClicknTranslate.exe` opened
"Failed to execute script 'pyiboot01_bootstrap' … Failed to setup PYZ archive reader!".
PyInstaller had reported success and the suite was green.

**What the evidence showed** (PyInstaller 6.20.0, Python 3.12.10, Windows 10.0.19045):

| Artifact | State |
| --- | --- |
| `build\ClicknTranslate\PYZ-00/01/02.pyz` | all three valid, `50 59 5A 00` magic |
| `build\ClicknTranslate\ClicknTranslate.pkg` | **valid** — PYZ magic at offset 178,943, no zero runs |
| GUI exe (build and dist, same bytes) | embedded `PYZ.pyz` had its **first 1,048,576 bytes zeroed** |
| `ArgosWorker.exe`, `OcrWorker.exe` | both fine, and both run |

The corruption was **zeroed in place, not shifted**: `embedded[1 MiB:] == PYZ-00.pyz[1 MiB:]`
byte for byte, and the zeroed region starts at the PYZ entry's offset inside the appended
archive, not at any file or section boundary.

So the standalone archive was correct and the copy inside the executable was not: the damage
happened while the archive was being appended, after which PyInstaller still exited 0.

**Not the cause** (each checked, not assumed):
- *UPX, the icon, the manifest* — a minimal spec reproducing all three (`icon` + `manifest` +
  `upx=True`, PYZ > 1 MiB) built clean.
- *Several EXE/PYZ in one spec* — the two worker executables in the same spec were never
  affected, and their PYZs are built by the same code.
- *A poisoned build cache* — the cached `.pkg` on disk was intact; the exe built from it was not.

**Reproducibility: none.** Rebuilding from the same spec, cache and toolchain produced a clean
executable, verified by reading the embedded archive back and by launching the app.

That leaves something touching the file between the write and the append — a running copy of
the app (one build in that session already died with `WinError 32` on `ArgosWorker.exe`), an
interrupted previous build, or the on-access scanner. Windows Defender is the active
antivirus on this machine and `C:\Users\Home-PC\Desktop\clickntranslate` is not excluded;
excluding the working tree is worth doing before a release build.

**The durable fix — the build now verifies its own output.** Both specs end with
`_verify_frozen_executables()`, which opens each shipped executable, extracts its embedded
PYZ and fails the build unless the payload starts with the `PYZ\0` magic. It names the file
and the number of leading zero bytes, and says what usually causes it. Proven both ways: it
accepts the real build and rejects the same build with a mebibyte zeroed at the PYZ entry.
Covered by `tests/test_build_integrity.py`.

**Also worth fixing: the smoke test that called the broken build healthy.** It only asked
whether the process was still alive after 8 seconds — and a PyInstaller bootstrap failure
keeps the process alive behind a modal error box. A smoke test has to inspect the window
titles (or drive the app), never just liveness.

### 13.4 Not verified — needs a real desktop session

**Correction (see §17): this WSL2 does have WSLg** — WSL 2.7.11 with WSLg 1.0.73.2 on Windows 10
19045, `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`. The Linux GUI runs and appears on the Windows
desktop, so the app itself can be driven. What still cannot be tested here is **screen capture**:
WSLg has no xdg-desktop-portal and no `grim`/`gnome-screenshot`/`spectacle`, and an X11 client on
Xwayland gets a black root window. The selection overlay and the portal path therefore still need
a real Linux desktop.

### 13.5 Build environment note

`.venv312` is required for **Windows** releases (`EASYOCR_PYTHON_VERSION`). The Linux spec does
not enforce a version yet — the WSL environment is Python 3.10. Before shipping a Linux build
that must support runtime EasyOCR/RapidOCR installs, decide which interpreter the Linux engine
installer targets and add the same guard to `ClicknTranslate-linux.spec`.

---

## 14. The settings window is a fixed size — read this before styling it

`SettingsWindow` and `OcrLanguageManagerDialog` are both fixed-size windows. Nothing can be
solved by giving a control more room: there is none. Two rounds of styling were spent
learning that, so it is written down here.

### 14.1 The drop-down fields have no outline, deliberately

The three pickers on the right (OCR / Translate / Show window) draw **no border**. Do not
add one back.

A 1px CSS border cannot render evenly here. Measured on the real display, `QComboBox.grab()`
in the focused state:

| display scaling | device pixel ratio | what Qt drew |
|---|---|---|
| 100% | 2.0 | 2 solid device px per edge |
| 125% | 2.5 | 2 solid px **plus a half-lit third row** (`#604e78` instead of `#a985d2`) |
| 150% | 3.0 | 3 solid px plus a partial row |

The half-lit row lands on one edge only, so that edge reads thicker and softer than the other
three — the field looks crooked. Painting the stroke on the device-pixel grid (whole device
pixels, rect snapped with `round(v * dpr) / dpr`) did fix the measurement, but the user's
verdict on the result was still "the outline is bad, delete it", so it is gone.

What replaces it, in `_engine_combo_style()`:

- the field reads as a field from its own darker fill (`#17181d` on dark, `#ffffff` on light)
  against the window;
- hover, focus and open lift that fill (`#221f2c` / `#f2eef8`) instead of drawing a line;
- `border: 1px solid transparent` stays in the rule — **not** `border: none` — so the box
  model keeps its 1px ring and the text does not shift by a pixel between states.

Locked in by `tests/test_settings_appearance.py::DropDownFrameTest`: the field must be one
flat colour from its first row of pixels to its last, no rule may contain a coloured border,
and opening the list must still change the fill.

### 14.2 Things that are already correct, so do not "fix" them

- **Field margins are symmetric** (`margin-left`/`margin-right: 3px`). They were 6/0, which
  put the box flush against the widget edge.
- **The lists open below the field**, 3px clear of it (`DropDownCombo.showPopup`). Qt's
  default lines the current row up with the closed control, so a long list covered the field.
- **The package tables snap to whole rows** (`_snap_table_to_whole_rows`). Measure only while
  the table is uncapped, once the layout has settled — measuring a capped table and capping it
  again shaves a row off on every pass.
- **Tab bars carry their own font** (`_apply_tab_bar_font`). A tab bar measures its tabs with
  the widget font and paints them with the stylesheet font; with the size declared only in the
  stylesheet, every tab was sized for the 6pt default and the labels ran over each other.

### 14.3 A NameError in a paint handler kills the process

`main.py` imports names *from* `PyQt5.QtGui`; it does not import the module. A `QtGui.QPainter`
reference inside `paintEvent` therefore raises `NameError`, and PyQt turns an exception in a
virtual method into `qFatal` — the process aborts with no traceback and no output at all. If a
window dies silently right after a paint-related change, that is the first thing to check.

### 14.4 Engines are installed and removed in Language packages, not in the picker

The OCR and Translate pickers used to carry a 16px `×` that removed the selected
engine. It is gone. Each engine's tab in Language packages now has a **Remove engine**
button at the top right, opposite the note, where installing it already lived:

| tab | install | remove |
|---|---|---|
| Windows | Windows Features on Demand | — (belongs to the OS) |
| Tesseract / EasyOCR / RapidOCR | empty-state card | top-right button |
| Hy-MT | empty-state card | top-right button |
| Argos | per direction, in the table | — (per direction) |

Hy-MT had no tab at all, which is why the `×` could not simply be deleted: removing it
would have left Hy-MT with no way to be uninstalled. It has its own tab in the
Translation section now, listing the engine and its local model.

Two things that will catch you here:

- **The dialog's own stylesheet loses to the settings window's.** `OcrLanguageManagerDialog`
  is a child of `SettingsWindow`, and an ancestor's more specific selector wins over an
  ID rule set on the dialog. Buttons inside the tabs therefore carry their own stylesheet
  (`_engine_remove_button_style`), the same way the Install/Remove-language buttons always
  have.
- **`_populate_hymt_table` probes the owner defensively** (`getattr(self.owner, "_hymt_installed", None)`).
  A stub owner that lacks a probe means "not installed", not a crash while the dialog is
  being built.

### 14.5 Labels are sized from their own text, not from a fixed number

"Copy translated text automatically" was clipped in Russian and Spanish: the check box was
a flat `min-width: 260px` and shares its row with the Show-window picker, so the overflow was
drawn over by that control. The word "automatically" is gone from all six languages (it only
restated what the setting does), and the box is now sized from `sizeHint()` in
`_fit_copy_translated_checkbox`, called from `apply_theme` — the theme sets the font it is
measured with, so it cannot be worked out at construction time. 260px stays as a floor so
the English window is unchanged. Covered by
`test_the_copy_checkbox_label_is_never_clipped`.

### 14.6 The package manager is kept alive between openings — retranslate it

`SettingsWindow._language_manager_dialog` caches `OcrLanguageManagerDialog`, and that dialog
builds every string once, from `self.lang` captured in its constructor. Switching the
interface language therefore left it in the old language until the app restarted — the
settings window went Spanish while the packages window stayed Russian.

`update_language()` now calls `_relanguage_language_manager()`, which throws the dialog away
and builds a new one when the language no longer matches. It keeps the open section and
engine tab and the window's geometry, so the user lands where they were. `show_ocr_language_manager()`
does the same check before reusing a cached dialog.

The one exception: **an install in progress is never swapped out** — that dialog owns the
progress window and the worker's cancel flag. It is left alone and replaced the next time it
is opened. Covered by `LanguageManagerFollowsInterfaceLanguageTest`.

If you add another long-lived dialog, it needs the same treatment; everything else in the app
is built per-open and picks the language up for free.

---

## 15. Windows OCR installs: what the numbers mean

Installing a Windows OCR language is `dism.exe /Online /Add-Capability` against a Feature on
Demand that Windows Update has to fetch. Two properties of that mechanism drive the whole
design:

1. **Microsoft promises no ETA.** Its OCR and PowerToys documentation says installation may
   take several minutes; measured DISM runs on this machine sat on one component percentage
   for several minutes and took as long as 16.5 minutes for one language.
2. **CBS.log has two different signals, neither is an ETA.**
   `%windir%\Logs\CBS\CBS.log` gets
   `DownloadProgress: [ 49 / 100 ]` written every couple of seconds while the payload comes
   down. Whether that file is still growing is how you tell "slow" from "wedged" — it is the
   diagnostic used here. Log growth only proves the service is responding: Windows can repeat
   the same `94 / 100` line for ten minutes. Only a changed download/DISM percentage is actual
   progress. The CBS value is scoped from the start of the current component and presented as
   **Windows Update download**, never as the remaining time or whole-job progress.

### 15.1 What the installer script reports

`_windows_ocr_installer_script` runs elevated, so it can read CBS.log. Its status JSON now
carries three fields beyond the percentage:

| field | meaning |
|---|---|
| `download` | last `DownloadProgress: [n / 100]` from CBS.log, or `-1` when unknown |
| `quiet` | seconds since either dism's component percentage or the download percentage changed |
| `restart` | dism answered 3010 — installed, but Windows wants a reboot |

Only the tail of the log is read (64 KB, `FileShare::ReadWrite`, seek from the end) and only
every ~2 s (`$tick % 8`), while the loop itself keeps spinning at 250 ms so Cancel stays
responsive. Reading it whole every tick would cost more than the install.

### 15.2 What the user sees

- **Before starting:** the realistic expectation — 5–20 minutes per language, the percentage
  will sit still, it is Windows Update doing it, and it keeps going in the background because
  the work belongs to a Windows service.
- **While running:** `Language N/M`, one of four stages (check, Basic, OCR, verify), elapsed
  time, Windows Update's named download percentage (when available), and whether Windows is
  still responding. The bar is explicitly the percentage of the **current DISM component**.
  There is no synthetic whole-job percentage: Basic and OCR do not
  take equal time, so the former 50/50 calculation produced convincing but false values such
  as 33%. The dialog states that Windows Update controls the remaining time.
- **After 5 minutes without changed progress** (`WINDOWS_OCR_QUIET_WARNING_SECONDS`): a line
  says that Windows is still responding but the download may be stalled, and offers the two
  honest choices: keep waiting in the background or cancel safely. Repeated identical CBS lines
  no longer reset this timer.
- **On 3010:** the language is reported as pending a restart instead of ready, because the OCR
  engine will not see it until the machine reboots.

The Windows OCR progress dialog reserves its final 560 px layout and a five-line message area
before the first frame. It therefore neither clips the stall explanation nor jumps from a small
window to a large one when installation begins. Other installers retain dynamic sizing.

Covered by `tests/test_windows_ocr_progress.py`.

### 15.3 "Restart Windows and try again" was usually wrong

A failure whose text merely contained the word **restart** was reported as
`win_error_service` — "Windows component servicing is busy or needs a restart. Restart
Windows and try again." A user hit it on a machine with **no pending reboot at all**: CBS
`RebootPending`, CBS `PackagesPending` and WU `RebootRequired` were all absent. The advice
sent them to reboot for nothing.

Three changes:

1. **The advice is checked against the machine.** `_windows_reboot_pending()` reads those three
   registry keys directly (no extra DISM session) and picks between `win_error_restart` and
   the new `win_error_busy`, which says to wait a minute and retry and that no restart is
   needed. `0x800f0902` (another servicing operation is running) maps here too.
2. **The raw text goes behind Details** in the failure dialog, and stays in the log
   (`_last_task_error_details`). Before this, diagnosing a failure meant reading
   `C:\Windows\Logs\DISM\dism.log` by hand — which is how this one was found.
3. **Our own queries and the full elevated servicing run are serialised.** `dism.log` showed three `Get-WindowsCapability`
   sessions against the online image inside the same second — the package tab, the runtime
   probe and the post-install verification all asking at once. Overlapping sessions on the
   online image are a cause of "servicing is busy", so every query now goes through the
   module-level `_WINDOWS_SERVICING_LOCK`; the elevated installer/remover holds that same lock
   until it exits. Reopening Language packages during a running install skips refresh/probe
   calls rather than queueing another DISM session.

When triaging one of these, note that `dism.log` records **every** DISM session including our
read-only probes. If there is no `Add-Capability` entry near the failure, the install never
reached dism and the fault is earlier — in the elevated script, in elevation itself, or in a
query that threw.

### 15.4 The generated PowerShell must be parsed by PowerShell in tests

The install failure in §15.3 turned out to be **our bug, not Windows'**. The restart-pending
line was written into the installer script as:

```
$resultText = if ($Script:RestartRequired) { 'OK_RESTART' } else { 'OK' }
```

These scripts are built with f-strings, where a literal brace has to be **doubled**. A single
one is not a Python error — `{ 'OK_RESTART' }` is a perfectly valid f-string expression — so it
was evaluated and spliced in bare:

```
$resultText = if ($Script:RestartRequired) OK_RESTART else OK
```

PowerShell rejected the file with `MissingStatementBlock` before running a line of it, which is
why `dism.log` showed no `Add-Capability` anywhere near the failure.

Two guards now:

1. `tests/test_windows_ocr_progress.py::GeneratedPowerShellParsesTest` writes every generated
   script to a temp file and runs
   `[System.Management.Automation.Language.Parser]::ParseFile` over it (Windows only; the
   brace-balance check runs everywhere). Verified to fail on the broken line and pass on the
   fixed one.
2. The error mapper no longer treats a parse error as a Windows state — `ParserError`,
   `MissingStatementBlock` and friends map to the generic message, and the reboot heuristic
   matches `restart` / `reboot` as **whole words**, so the string `OK_RESTART` inside a quoted
   line is not a verdict about the machine.

**When editing these scripts, remember every literal `{` and `}` must be doubled.** The tests
will catch it now, but the failure mode is silent at the Python level.

### 15.5 Background work stays visible without a notification sound

"Continue in background", the title-bar close button and the package manager's Back button
now all preserve the same running task. The package manager shows a persistent one-line state
and a localized **Show** button that restores the original progress window. If the manager is
closed, the Settings **Language packages** button carries the localized word **Installing**,
then a green localized **Done** on success or `!` on failure; its tooltip has the full status.
Opening Language packages acknowledges and clears **Done** (the failure marker remains visible).
A raw component value
such as `58%` is deliberately not placed on that button because it looks like whole-job progress.

This deliberately does not use a Windows toast: those can play the system notification sound,
and Click'n'Translate is required to remain silent. Completion is visible on the normal route
back to the package manager without stealing focus. Covered by
`BackgroundProgressCanBeReopenedTest`, the two package-manager close-route tests and the
settings-button status test.

### 15.6 One package mutation at a time

While any package install/removal is active, every install/remove/engine action and **Refresh**
is temporarily disabled. Tabs, tables and checkboxes stay usable, so the user can prepare the
next selection without losing it. **Show** restores the existing progress dialog. A second call
that gets through programmatically restores the first task and returns; it is never silently
queued, because an automatic follow-up minutes later could unexpectedly trigger another UAC
prompt. Controls return to their previous enabled state when the task finishes.

## 16. Fixed-window text must not be one compressible rich-text label

The Settings action occupies one third of a 700 px window. While a task badge is present it uses
the localized short base (`Packages`, `Пакеты`, etc.); the full `Language packages` label returns
when idle. This prevents `Language packages · Installing` from losing its first/last letters.

The four hotkeys on the main screen are separate caption/value label pairs, each sized from its
real font metrics, given a 22 px text height, and given 5 px of trailing glyph room. That last
margin is intentional: `horizontalAdvance()` excludes the anti-aliased right edge of a bold
final `C`, `F`, `T` or `Q`, so an exactly-sized label visibly shaves the letter. Do not recombine
them into one rich-text QLabel
with `&nbsp;`: the layout can compress that label to make room for the OCR/translator name and Qt
then clips individual shortcut characters without any ellipsis or warning.

---

## 16. The Linux release — built and verified (1.5.6)

`tools/build_linux_release.sh` produced all three artifacts on Ubuntu 22.04 (WSL2), x86_64,
Python 3.10.12, PyInstaller 6.21:

| Artifact | Size |
| --- | --- |
| `Click-n-Translate-1.5.6-linux-x86_64.AppImage` | 255 MB |
| `Click-n-Translate-1.5.6-linux-x86_64.tar.gz` | 253 MB |
| `Click-n-Translate-1.5.6-linux-x86_64.sha256` | both checksums |

They are in `releases/`, and the checksums were re-verified after copying to the Windows side.
Release notes: `releases/v1.5.6-linux-notes.md`.

### 16.1 What was verified

* **Unit suite on Linux** — 501 passed, 30 skipped (the skips are Windows-only tests: Windows OCR,
  the servicing lock, the update flow).
* **`tools/functional_check.py --frozen dist/clickntranslate --offline`** — 47 passed, 0 failed,
  11 skipped. Including:
  * the **packaged ArgosWorker translating offline**: `Привет, мир! Как дела сегодня?` →
    `Hello, world! How are you today?`, with no torch and no onnxruntime in the bundle;
  * the packaged worker **installing** `ru→en` on request (it survived a transient
    `URLError(TimeoutError)` and retried);
  * **bundled RapidOCR** reading text from an image at similarity 1.00;
  * the command socket, autostart entry, `.desktop` install and capture-action entries.
* **The AppImage itself** — starts, creates `clickntranslate.sock`, and a second launch with
  `--ocr` delivers the command and exits 0 while the first instance keeps running. That is the
  mechanism every Linux shortcut depends on.
* **Build integrity** — the spec's `_verify_frozen_executables` reported
  "Verified embedded archives in 3 executables", so the 1.5.4-class PYZ corruption is ruled out
  for this build.

### 16.2 Still needs a real desktop session

Screen capture on X11 and Wayland, the selection overlay, the tray icon, and desktop shortcut
binding. WSL2 on Windows 10 has no WSLg, so there is no display to test against — the Wayland
portal path in particular is written against the spec and reviewed, not run.

### 16.3 A trap in the functional check, now fixed

`packaged argos worker translates` reported **FAIL** on a machine with no language package
installed. The worker answers `{"result": null, "error": ""}` in that case — no error, no text —
and the check only skipped when `error` was set. A missing prerequisite is a skip, not a failure;
otherwise every fresh build machine shows a red line that means nothing. Fixed in
`tools/functional_check.py`.

### 16.4 Two things to know about driving WSL from this repo

* **`pkill -f clickntranslate` kills your own shell.** `-f` matches whole command lines, and the
  repo path contains the word. Use `pkill -x clickntranslate`.
* **Background jobs started with `wsl.exe -- bash -lc '... &'` die with the session.** Use
  `setsid nohup ... < /dev/null &`, or run the command synchronously.

---

## 17. Running the Linux build on a real display — three defects it found

**This WSL does have WSLg** (WSL 2.7.11, WSLg 1.0.73.2, Windows 10 19045): `DISPLAY=:0`,
`WAYLAND_DISPLAY=wayland-0`, and a Linux window appears on the Windows desktop. §13.4 said
otherwise; that note is now corrected. Launch it with
`.tmp/run_linux_gui.sh` (copy into WSL, `tr -d '\r'` first).

Running the shipped AppImage on that display found three things no headless run could.

### 17.1 The AppImage could not start at all

```
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
```

`ldd` on the bundled `libqxcb.so` showed six unresolved sonames: `libxcb-icccm.so.4`,
`libxcb-image.so.0`, `libxcb-keysyms.so.1`, `libxcb-render-util.so.0`, `libxcb-shape.so.0`,
`libxcb-xinerama.so.0`. PyInstaller follows the dependencies of the *executable*, not of a plugin
it merely copies, so nothing pulled them in — and the build machine did not have them either, so
there was nothing to copy.

Fixed in three places: `ClicknTranslate-linux.spec` resolves them from `ldconfig -p` and bundles
them, **failing the build with the apt line if any are missing** (shipping without them produces
an AppImage that cannot open a window, and nothing else reports it); `tools/setup_linux_env.sh`
installs them; `libxcb-util1` and `libxkbcommon-x11-0` are included for the same reason.

### 17.2 White bands down both sides of every drop-down

The list is styled through the combo's stylesheet, but Qt wraps it in a **window of its own**, and
on Linux that frame keeps the platform default — white. `DropDownCombo.set_popup_background()`
paints it, and `_apply_engine_combo_style` sets it per theme. Windows never showed this because
the frame there already matches the list.

### 17.3 EasyOCR could not install: pins for the wrong interpreter

```
ERROR: Could not find a version that satisfies the requirement scipy==1.18.0
       (from versions: 1.7.2 ... 1.15.3)
```

`EASYOCR_PIP_PACKAGES` is an exact tree resolved for the Python **the Windows installer
downloads** (3.13). On Linux the installer uses the distribution's interpreter — 3.10 on Ubuntu
22.04 — where most of those pins have no wheel, so pip refused before installing anything. This
was latent on Windows too: a system Python older than 3.13 would have failed the same way.

`_easyocr_requirements()` now asks the target interpreter for its version
(`_pip_target_python_version`) and returns the pinned tree only when it is at least the version
the tree was resolved for. Otherwise it uses `EASYOCR_PIP_PACKAGES_ANY_PYTHON`: EasyOCR itself
pinned, the rest left to pip. `--only-binary=:all:` still applies, so it stays wheels-only.

### 17.4 Capture still cannot be tested here, and now says so

WSLg has no `xdg-desktop-portal` and none of `grim`/`gnome-screenshot`/`spectacle`, and an X11
client on Xwayland gets a **black root window**: `grabWindow(0)` returned a full-size 2560x1440
image with exactly one colour in it. The app used to hand that on as a screenshot, so OCR
answered "no text found" — the wrong answer to the wrong question. `linux_capture.looks_blank()`
now catches an all-black grab and raises with `blank_grab_message()`, which names the portal
package and the X11 way out. Only black counts, so a plain coloured desktop is not mistaken for a
failure.

Real capture, the selection overlay and the tray still need a Linux desktop with a portal.

---

## 18. "It lags" on Linux — what was measured

Same window, same code, measured on both sides rather than guessed at.

| Measurement | Windows | Linux (WSLg) |
| --- | --- | --- |
| Painting the settings window (60 frames, off-screen) | 2.1 ms/frame | **0.9 ms/frame** |
| Idle CPU, nothing open | 0.0% of a core | 0.0% of a core |
| Idle CPU, welcome/News dialog open | (not open) | **9.8% of a core** → 0.0% after the fix |
| Resident memory | 116 MB | 262 MB (frozen build) |

**Our painting is not the problem** — it is twice as fast under WSLg as on Windows, because it is
plain CPU rasterisation either way and the machine has 16 cores.

### 18.1 The one real defect: an endless blur animation

`WelcomeDialog._pulse_flag_button` animated a `QGraphicsDropShadowEffect` with
`setLoopCount(-1)`. A blurred drop shadow is re-rendered in software on **every frame**, forever,
for as long as that dialog stayed open — 9.8% of a core, on the window the user sees first. On
Windows the same code costs little enough to disappear into the noise, which is why it survived
this long.

The pulse now runs eight cycles and then removes the effect. The guide's target glow was the same
construct and is gone entirely: the spotlight added in §14 dims everything around the target, so
the glow it drew was not even visible, and the spotlight's ring is a stroked rectangle rather than
a blur. Locked in by `IdleCostTest` — no endless animation may drive a `QGraphicsDropShadowEffect`.

### 18.2 What is genuinely WSL, and cannot be fixed here

WSLg composites through Weston and ships frames to Windows over RDP, with input travelling back
the same way, and Qt has no GPU there. That latency is inherent to running a Linux GUI inside WSL
and does not exist on a real Linux desktop. It also cannot be measured from inside the process:
`repaint()` under xcb queues to the X server and returns, so app-side timers report ~0 ms while
the frame is still in flight.

Also worth knowing: `--appimage-extract-and-run` unpacks 255 MB into `/tmp` **on every launch**.
That is start-up cost, not lag. A normal AppImage run mounts through FUSE and starts immediately;
the extracted `dist/clickntranslate/clickntranslate` starts instantly too.

### 18.3 Hotkeys cannot be tested under WSLg

By design there are no in-app global hotkeys on Linux (§13.1) — the user binds a command in their
desktop's shortcut settings. WSLg has no desktop and no shortcut UI, so there is nothing to bind
them in. The mechanism a shortcut would use is testable directly, and works:

```
/root/cnt/dist/clickntranslate/clickntranslate --ocr     # delivers to the running instance, exits 0
```

---

## 19. Testing on a real Linux desktop, and the four bugs it found

WSLg alone is not a desktop: no compositor of the kind apps expect, no portal, and an X11 client
sees an empty root. A **nested X server** is: `Xephyr` gives a genuine X11 root window that owns
every window inside it, and `openbox` on top makes it a desktop with focus, decorations and key
bindings. It runs in a window on the Windows desktop and needs no VM.

```
apt-get install -y xserver-xephyr openbox x11-utils xdotool x11-xserver-utils
```

`.tmp/linux_desktop.sh` starts it: Xephyr on `:7`, openbox with `Ctrl+Alt+O/C/T` bound to
`clickntranslate --ocr/--copy/--translate`, and the app inside. This is the first environment
where the Linux build could actually be exercised.

### 19.1 EasyOCR installed but could not be imported

`No module named 'pickletools'`, then `timeit`, then `unittest.mock`. EasyOCR and torch are
installed **at runtime**, so PyInstaller never analyses them and bundles only the stdlib that our
own code imports. torch reaches for whatever it likes.

Both specs now call `_stdlib_hiddenimports()`, which expands every standard-library package into
its submodules (502 modules) and hands them to the OCR worker. Naming them one per rebuild does
not converge — each round costs eight minutes and a 1.3 GB install to reproduce. Verified by
asking the frozen worker to import the real installation: `{"available": true, "error": ""}`.

### 19.2 The selection overlay was a black rectangle

The overlay is translucent, and translucency only works where a compositing manager runs. GNOME
and KDE composite; openbox, i3 and a bare XFCE do not, and there the user would drag a selection
box across a solid black screen. Flameshot and NormCap both select on a frozen screenshot for
this reason, so `ScreenCaptureOverlay._freeze_required()` now returns True on Linux whatever the
"freeze screen" setting says. Windows keeps the setting.

### 19.3 Capture asked the environment instead of Qt

`WAYLAND_DISPLAY` is exported by the WSLg session and by every Wayland login, including for
processes that talk X11 — every Xwayland app is one. Capture read that variable, decided it was
on Wayland, went to the portal, found none, and failed **on a display where the plain X11 grab
works**. `grab_screen()` now asks Qt which platform it actually connected to: on `xcb` it grabs
the root first and only falls back to the portal if that comes back empty.

### 19.4 A black desktop is not a failed capture

The blank-grab guard from §17.4 was too eager: openbox draws no wallpaper and the app hides
itself before capturing, so the grab is legitimately all black and capture was refused. An
all-black grab is now logged with the explanation and **returned** — the portal is tried first,
and if there is none, a dark screenshot is a better answer than an error. OCR finding no text
says the same thing without inventing a cause.

### 19.5 Verified on that desktop

* the app opens its window and runs at 0.0% idle CPU;
* `Ctrl+Alt+O`, bound in the window manager exactly as a user would bind it in GNOME or KDE,
  launches `clickntranslate --ocr`, which hands the command to the running instance and exits;
* the running instance opens its capture overlay with a **frozen background** captured through
  the app's own path (`Frozen background captured; size=1600x900`);
* the screenshot of that desktop, taken with the app's own capture code, contains the overlay and
  its language picker;
* EasyOCR imports in the frozen worker.

### 19.6 Two ways to waste half an hour here

* **Two builds at once.** Starting a rebuild while another is running leaves `dist/` half from
  each, and the binary keeps its old timestamp while the log says the build finished. Poll the
  binary's mtime, not the log, and never `pgrep -f build_linux_release` — that matches the shell
  running the check.
* **`&&` chains in a backgrounded WSL command.** `rsync && grep && build &` silently skips the
  build when the grep finds nothing.

---

## 20. Real Wayland portal and Linux package completion (2026-08-09)

WSLg itself has no usable Screenshot portal, so a nested Sway compositor was started with its
own user D-Bus session, PipeWire and `xdg-desktop-portal-wlr`. This is a real 1280×720 Wayland
output using Qt's `wayland` platform plugin, not `offscreen` and not mocked DBus.

That run found two defects in `linux_capture.capture_with_portal()` which no unit test or helper
fallback exposed:

1. `QDBusConnection.connect()` only accepts a bound `QObject` method decorated as a Qt slot. The
   old nested Python callback raised `TypeError` as soon as a real portal was present.
2. The portal's Response signature is exactly `uint, a{sv}` (`"uint", "QVariantMap"` in PyQt),
   not signed `int`. Also, wlroots can emit Response before the Screenshot method returns, so the
   listener must be connected to the deterministic request path **before** making the call.

After the fix, both a direct portal probe and the packaged application's real `--ocr` flow
received a non-empty 1280×720 image. The frozen app accepted `--show` and `--ocr` from a second
process, logged `qt platform=wayland, portal=True`, captured the frozen background and displayed
the overlay.

The AppImage packaging was also completed:

* AppStream metadata is installed and passes `appstreamcli validate --pedantic`;
* the launcher uses the lower-case reverse-DNS desktop ID
  `io.github.jabrailkhalil.clickntranslate.desktop`;
* installing the launcher or autostart entry removes the old short-name `.desktop` file, so an
  upgrade cannot leave duplicate menu entries;
* desktop categories now use one main category (`Utility`) plus `Qt`, avoiding duplicate menu
  placement, with search keywords for translation, OCR, capture and text.

`.tmp/linux_wayland_test.sh` recreates the Wayland test. It also runs the packaged binary after
the capture probe. `.tmp/linux_desktop.sh` and `.tmp/nested_full_check.sh` cover the separate X11
desktop.

There is no Hyper-V, VirtualBox or VMware VM configured on this machine (`Get-VM` is empty and no
VM hypervisor tooling is installed). Xephyr and Sway exercise the genuine X11 and Wayland
protocols, but tray/permission UX on a full GNOME or KDE installation still needs a short manual
pass on that target desktop.

Final local verification for this tree: Windows 561 passed / 11 skipped; Linux 538 passed / 34
skipped; frozen functional sweep 54 passed / 0 failed / 4 optional skips. The extracted X11
binary reached its command socket in 187 ms and a visible window in 402 ms, then used 0.2% CPU
over a ten-second idle sample (248 MB resident in the WSL build).

---

## 21. Release 1.5.7 — Windows and Linux completion (2026-08-10)

Version 1.5.7 is the first release built and checked from the same tree for both
Windows and Linux.

### 21.1 User-facing changes

* `Ctrl+Alt+M` is the new configurable show/hide shortcut. A window minimized
  to the taskbar returns to the taskbar; a window hidden in the tray returns to
  the tray. Linux exposes the same action as `--toggle` and in its desktop menu.
* The settings hotkey page has five complete rows and reset restores the new
  default along with the existing four shortcuts.
* The source and target language lists on the main screen show nine complete
  rows, use a branded selection and a thin draggable scrollbar. A local
  `QProxyStyle` disables GTK's native menu popup because Qt documents that GTK
  ignores `maxVisibleItems` and adds its own large scroller buttons.
* Linux system helpers no longer inherit PyInstaller/AppImage library paths.
  That prevents the bundled `libstdc++` from breaking the host Tesseract and
  clipboard/screenshot tools.

### 21.2 Reproducible Linux packaging

AppStream validation is now local and deterministic:
`appstreamcli validate --no-net` runs before `appimagetool --no-appstream`.
The metadata remains inside the AppImage, but a slow external project URL can
no longer fail a release build.

### 21.3 Real GNOME VM verification

A dedicated Ubuntu 24.04 Hyper-V VM ran the AppImage through FUSE in its normal
GNOME Wayland session. Verified there:

* main window startup and one running application instance;
* `--toggle` hides the visible window completely and restores it at the same
  size and position;
* first-invocation OCR, RU/EN language switching, real region capture and exact
  Tesseract recognition of `Hello world OCR test`;
* installed `eng`/`rus` discovery from the host Tesseract;
* the final nine-row language popup, complete last row, application-coloured
  selection and scrollbar drag from the first languages to the final Hindi row.

### 21.4 Final verification

| Layer | Result |
| --- | --- |
| Windows source suite | 568 passed, 11 platform/optional skips, 8 subtests |
| Linux source suite | 545 passed, 34 platform/optional skips, 8 subtests |
| Windows frozen functional sweep | 34 passed, 0 failed, 6 optional skips |
| Linux frozen functional sweep | 56 passed, 0 failed, 3 optional skips |
| Windows updater E2E | portable and installed 1.5.6 -> 1.5.7 passed |
| Updater safety | user data preserved; locked OCR worker stopped; app restarted |
| AppStream | local no-network validation passed |

The updater E2E uses a disposable copy of the public 1.5.6 portable release and
a disposable Inno AppId. It verifies the shipped 1.5.7 ZIP and new
`app/_internal` layout, not a mocked payload.

### 21.5 Release artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `Click-n-Translate-1.5.7-windows-portable-x64.zip` | 204702413 | `5d82079cff4c3068f34ed33264e5c6eed384f899f4e8ddd1aa5f31388a048b71` |
| `Click-n-Translate-1.5.7-windows-x64-installer.exe` | 128419533 | `f03b42e3405243ed6885a5d259143c3ecc985b2e1add28b30260897dc2edabff` |
| `ClicknTranslate-Setup-v1.5.7-win64.exe` | 89600 | `5962954b918484f2793bb659dcc81455de861c43d4262a5b356dc913cd54510c` |
| `Click-n-Translate-1.5.7-linux-x86_64.AppImage` | 273876160 | `794c86e08cb41a4c69eed082c72ffaeaa57818399c9e5fcdbb2a4c9299990846` |
| `Click-n-Translate-1.5.7-linux-x86_64.tar.gz` | 271678168 | `64bda9af63dbee7426fcfddcf2266bf16327ff7da747af96caaee187ba588675` |

---

## 22. Release 1.5.8 — workflow and UI completion (2026-08-11)

### 22.1 User-facing changes

* Each hotkey mode can use its own remembered source/target language pair.
* Windows can optionally replace selected text with its translation. Focus and
  selection are rechecked before paste; unsafe cases fall back to copying.
* The main text field now has a compact messenger-style send action and opens
  the dedicated document workspace from its document icon.
* The document workspace, onboarding guide, hotkey legend, dropdowns, and
  settings layout were polished and fully localized.
* Long-lived dialogs now resync both language and theme when reopened. This
  includes the document workspace reopening correctly in the light theme.

### 22.2 Final verification

| Layer | Result |
| --- | --- |
| Windows source suite | 632 passed, 11 skipped, 8 subtests |
| Linux source suite (WSL) | 609 passed, 34 skipped, 8 subtests |
| Windows frozen functional sweep | 30 passed, 0 failed, 10 optional skips |
| Linux frozen functional sweep | 52 passed, 0 failed, 7 optional skips |
| Windows updater E2E | portable and installed 1.5.7 -> 1.5.8 passed |
| Updater safety | user data preserved; locked OCR worker stopped; app restarted |
| Portable ZIP layout | 4004 entries; one top-level folder; launchers/workers/icon present; no user data |
| Linux AppImage | AppStream validation passed; extract-and-run stayed healthy for 15 seconds |

The current WSL image does not contain `libfuse.so.2`, so direct AppImage FUSE
mounting was not available there. The official `--appimage-extract-and-run`
fallback started successfully; the frozen Linux functional sweep also passed.

### 22.3 Final artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `Click-n-Translate-1.5.8-windows-portable-x64.zip` | 204823199 | `E45175C40277345A803BBD68340D17B0AE70941D4AB054A007227B39BBEDA817` |
| `Click-n-Translate-1.5.8-windows-x64-installer.exe` | 128503765 | `E9025E6788B6A5A0443CC8AA4E28B0B357DD1EEDF617C70AD9209600F8D9AFEA` |
| `ClicknTranslate-Setup-v1.5.8-win64.exe` | 89600 | `93A61E198DBC3CE48B080917FA887D3EF87251195951440ADF95A9683D237835` |
| `Click-n-Translate-1.5.8-linux-x86_64.AppImage` | 273962176 | `131FC838714F06464FA8EBC1623707556D9716C069148BBB6FF5C922F94C0C81` |
| `Click-n-Translate-1.5.8-linux-x86_64.tar.gz` | 271609750 | `E16BD44E164C616C54B7222C0AB853D2076081CA1E8A5C6A5E97DBB732F3BE6E` |

---

## 20. The main window: measured, then rearranged

The complaint was that it is overloaded and does not say where to start. Measured on the shipped
layout (700x400, 350px of content):

| block | height |
| --- | --- |
| hotkey language bar, with its own hint line | 59 |
| source language, full width | 32 |
| target language, full width | 32 |
| **text box** | **56** |
| Translate (outlined) | 39 |
| shortcut legend, two rows | 47 |
| Shadow mode (solid accent) | 35 |

**126px of language pickers against 56px for the thing the window is for**, three near-identical
purple rows competing at the top, and the only filled button on the screen was the one that sends
the window away. Nothing pointed at the task.

### 20.1 What changed

* **One direction row.** Source and target sit side by side with an arrow, as a pair, instead of
  two stacked full-width combos: 64px → 32px, and it reads as one setting.
* **The hotkey bar moved below the Translate button**, under a divider. It was first, so the first
  thing the eye met was the control you need least. Its hint sentence is the bar's tooltip now —
  the mode combo already reads "Translate and replace · Ctrl+Shift+Q".
* **The text box takes the freed space**: 56px → 103px, and it is now the tallest block.
* **The button emphasis is the right way round.** Translate is filled in the accent; Shadow mode
  is an outline. The outline colour follows the theme — light violet is invisible on white.
* **The text box border was dark red** (`#550000`), which reads as an error around the box you are
  meant to type in. It is a neutral hairline that turns accent on focus.

### 20.2 Two things measurement caught that a screenshot would not

* **The mode picker elided silently.** At a fixed 266px, German showed "Übersetzen und ersetzen ·
  Ctrl+Shi". Adding a hand-computed margin for the stylesheet padding and the chevron was wrong
  twice (44px, then 58px — still short). `_fit_hotkey_mode_combo()` asks Qt for
  `sizeHint()` under `AdjustToContents` and runs from `apply_theme`, because the font the text is
  measured with only exists once the theme is applied.
* **One line of shortcut chips does not fit.** It looked plausible and drew five chips on top of
  each other in Russian. Measured in all six languages: five chips plus the engine summary exceed
  690px in every one of them, so the legend stays two rows.

### 20.3 Testing this screen

`tests/test_main_window_layout.py` builds the window and checks the order, the single direction
row, the divider, that the text box is the tallest block, and that the legend keeps two rows. It
stubs `WelcomeDialog`, the launch update check and the first-run guide — a modal dialog in a test
run waits for a click that never comes.

**Pixel assertions do not belong there.** The offscreen platform draws no text, so its metrics are
fiction: it reports a 566px size hint for a combo that measures 305px on a real display. Anything
that depends on text width is checked by `.tmp/check_one_language.py`, which builds the window on
the real platform, one process per language, and reports what fits.

### 20.4 The legend listed five of six hotkeys

`translate_replace_selection_hotkey` (Ctrl+Shift+Q) is registered like the other five and works,
but nothing on the main screen mentioned it — the legend read five settings and stopped. It has a
chip now, under Window in the third column, with a short caption (`hotkey_replace`) in all six
languages; the settings screen keeps the full "Translate and replace selection".

`HotkeyLegendCoverageTest` compares the hotkeys read by the constructor against the ones read by
`show_main_screen` and fails on any that are registered but not shown, so a seventh hotkey cannot
be added and quietly left off the screen. It also fails if the constructor's list changes, which
is what tells you to update the caption table.

**Stop the app before running `tests/test_main_window_layout.py`.** A live instance owns the
single-instance handshake, and the second window these tests build waits on it forever — the run
looks like a hang with no failure.

### 20.5 Four more items, reported together after the redesign: tooltips of two different colours, a separator sitting on
top of the words, no keyboard way to translate, and content pressed against the window frame.

### 20.6 Tooltips were purple in some places and black in others

A widget with its own stylesheet resolves its tooltip against **that** sheet, so the app-wide
`QToolTip` rule in `install_tooltip_style()` never reaches it and the platform draws its default:
black, square corners. Every widget on the main window that both carries a tooltip and sets its own
stylesheet now appends `TOOLTIP_QSS` — the six title-bar buttons through
`styled_transparent_button_qss()`, plus the document button, the Translate button and the hotkey
bar.

The rounded corners needed a second thing. A top-level tooltip window paints its own background
under the rounded border unless it is told not to, so `border-radius` produced a purple rounded
rectangle on a black square. `styled_dialogs._RoundedTooltipFilter` watches for `QTipLabel` at
Polish time and sets `WA_TranslucentBackground` / `WA_NoSystemBackground` on it.

Checked with `.tmp/check_tooltips.py`, which shows each tooltip for real and reads its pixels:
border colour, and the alpha of the corner pixel (0 = the corner is actually cut). All eight
sampled tooltips report `purple=True translucent=True corner_alpha=0`. **The harness has to call
`main.install_tooltip_style(app)`** — that is what `main()` does at startup, and without it the
filter and the app-wide rule are simply not there, so everything looks black and the measurement
is meaningless.

### 20.7 The engine divider sat right next to the shortcut text

Two separate causes, both measured with `.tmp/check_separator.py` (per language: clear space
between the last chip and the panel's `border-left`, and the distance from that line to the text):

1. The gap before the line was the grid's horizontal spacing (10) and the gap after it was the
   panel's left margin (12 + 1px border = 13). Unequal, and the smaller one was on the side with
   the shortcut text.
2. `setColumnMinimumWidth(0, 160)` and `(1, 186)` were measured in English. French and Spanish
   ("Remplacer", "Reemplazar") overflow them, so the third column was pushed past the divider —
   in Spanish two chips ended up on the far side of the line. That is what "right next to the
   words" looked like.

The fixed column widths are gone; the columns take what their text needs. Both gaps are now 12
(13 after, counting the border) in all six languages. The row had to be paid for: at 672px of
content width Spanish needed 688, so the chips' `trailing_glyph_room` went 5 → 4, the keycap
padding 5px → 4px, and the spacing 16 → 12. Measured slack after that, in px:
en 7, ru 19, de 16, fr 15, es 9, zh 111.

`.tmp/check_row_width.py` prints what the row needs against what it has, per language. Run it
before touching any font, caption or padding in that row.

### 20.8 Enter translates, Shift+Enter starts a new line

`TranslateOnEnterTextEdit` (main.py) emits `translation_requested` on Return/Enter and falls
through to Qt when Shift, Alt or Meta is held. Ctrl+Enter still translates, which is what the box
did before. The translation result window is read-only and the document editor is for documents,
so neither changed.

The box's tooltip says so in all six languages ("Enter translates · Shift+Enter starts a new
line"), because a keyboard behaviour nobody can see is a keyboard behaviour nobody uses.

### 20.9 The content touched the frame

`main_layout` margins were `(5, 45, 5, 5)`: 5px from every edge, and the first row 5px under a
40px title bar. They are `(14, 52, 14, 14)` with spacing 8 — 14 all round, 12 under the title.

The window is fixed at 700x400, so those 20 vertical pixels had to come from somewhere: the
Translate button's padding 10px → 8px, Shadow mode's 6px → 5px, the hotkey bar's vertical margins
4 → 3, and the layout spacing 9 → 8. The text box still ends up the tallest block on the screen
(101px against a 96px minimum), which is the point of the redesign.

`.tmp/check_edges.py` prints the margins, the gap under the title, the gap at the bottom and every
block's distance from the right edge. `WindowEdgeTest` keeps the rule (sides equal, ≥12, and ≥8
below the title bar) so the next height problem is not solved by taking the margins back.

### 20.10 "Ruso → Inglés" at the top, "Inglés → Ruso" below

The window carries two direction rows and said nothing about either. The one at
the top belongs to the typed text; the one in the shortcut bar belongs to
whichever mode the picker beside it is editing — and **each of the four modes
keeps its own pair** (`ocr_translate_*`, `fullscreen_translate_from/to`,
`selection_translate_*`, `replace_selection_*`). A window reading Russian to
English at the top and English to Russian underneath looks broken; it is just
two different settings with no label.

`_direction_summary_text()` builds one line under the Translate button:

    Typed text: Russian → English      ·      Shortcuts: Russian → English

Modes sharing a direction are listed once, so the common case is one pair rather
than four repetitions. When they differ, each group names its modes:

    Typed text: RU → EN   ·   Shortcuts: RU → EN (OCR/Selection/Replace),  EN → RU (Fullscreen)

`_refresh_direction_summary()` fits it to the window, dropping detail in this
order: full names + mode names → **codes** + mode names → full names → codes.
Which mode does what is the point of the line, so the spelling of "English" goes
first. Measured on a real display, in 672px: 375px (en), 455 (ru), 331 (es), 380
(de), 357 (fr), 300 (zh) when the modes agree; 596–605 when they do not.

Two things to keep:

* It reads the config directly through `_stored_hotkey_pair()`.
  `_configured_hotkey_translation_pair()` inspects the installed OCR languages,
  and this label redraws on every combo change. A test fails if the summary ever
  reaches for `_available_hotkey_translation_pairs`.
* It is refreshed from `_refresh_selection_pair_hint()` and
  `_save_main_translation_languages()`, which is every path that can change
  either pair. `.tmp/check_direction_live.py` drives the real combos and prints
  the line after each change.

The text box paid for the line: `setMinimumHeight` 96 → 72 (it renders at 77 and
is still the tallest block).

`tests/test_main_language_persistence.py` borrows `DarkThemeApp` methods onto a
harness object — add any new method the pair setters call, or the harness raises
where the app does not.

The guide's `back_home` step used to say the main screen's pair was used by both
selection hotkeys. That has not been true since the shortcut row went in, and it
described the exact misconception this line exists to prevent. Corrected in all
six languages, and its test now checks the shortcuts are described as carrying
their own pair.
