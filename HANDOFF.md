# Click'n'Translate — 1.5.3 hotfix handoff

> **Purpose of this file.** A running, self-contained log of the 1.5.3 hotfix work so any
> other agent (Codex, Claude, a human) can pick the work up mid-flight without re-deriving
> anything. Keep appending to it. Do not delete history — mark items done instead.

**Last updated:** 2026-08-05 — all three reported issues fixed and verified; release staged but
**not published** (see §8).
**Working directory:** `D:\1python_projects\clickntranslate-main`
**Repo is NOT a git repository** (`git status` → `fatal: not a git repository`). There is no
version control safety net, so make backup copies before risky edits.
**Version in tree:** `app_version.py` → `APP_VERSION = "1.5.3"` (already bumped by a previous
agent; 1.5.2 is the last *published* release). README/build scripts already reference 1.5.3.

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

## 8. Status

**Done**
- [x] Issue #1 — full-screen translation fixed and verified end to end.
- [x] Issue #2 — OCR language install: real progress, responsive cancel, tolerant verification.
      Validated by a full 989 s live install (§3.4).
- [x] Issue #3 — update window redesigned, DPI-correct, visually verified at 150 % scaling.
- [x] Release blocker: created the missing `tools/build_apply_updater.ps1` (§5).
- [x] `.gitignore` root cause fixed (§9b).
- [x] Full test suite: **286 passed, 8 subtests passed** (`.venv`, Python 3.13).
- [x] `py_compile` clean on `ocr.py`, `settings_window.py`, `main.py`, `translater.py`.
- [x] PyInstaller build (Python 3.11) + `stage_release.ps1 -SkipPyInstaller -Version 1.5.3`
      completed. Staged package verified — all five required artifacts present:

      ClicknTranslate.exe                              87,040 bytes  v1.5.3.0
      app\ClicknTranslateApp.exe                   11,255,439 bytes
      app\_internal\ArgosWorker.exe                 9,951,334 bytes
      app\_internal\OcrWorker.exe                   7,778,907 bytes
      app\_internal\ClicknTranslateUpdater.exe        104,960 bytes  v1.5.3.0
      total package: 480.0 MB

- [x] Portable ZIP built (not published):
      `releases\Click-n-Translate-1.5.3-windows-portable-x64.zip`
      201.3 MB, sha256 `84e9b6ba5ceee57c271eae8de6fe08047d4638ab9d250dfbedc7c5a68cd43660`
      (This digest is for *this local build*. If the release is rebuilt, recompute it and update
      `tools/build_update_repair.ps1 -PackageSha256`.)

**Not done — needs the maintainer**
- [ ] **Installer `.exe` cannot be built on this machine: Inno Setup (`ISCC.exe`) is not
      installed.** The READMEs link to `Click-n-Translate-1.5.3-windows-x64-installer.exe`, and
      `tools/build_update_bootstrap.ps1` requires the Setup executable as its input, so the
      release asset set is incomplete without it.
- [ ] **Publishing the GitHub release was deliberately NOT done.** `gh` is authenticated as
      `jabrailkhalil` with `repo` scope, so it is technically possible — but publishing v1.5.3
      pushes this build to every existing 1.5.x user through the in-app updater. That is an
      outward-facing, hard-to-reverse action and needs an explicit decision, especially with the
      installer asset missing.
- [ ] The tree is **not a git repository**, so none of these changes are committed anywhere.
      `git init` + an initial commit is worth doing before anything else.

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

## 10. Release procedure (not yet run)

```powershell
# 1. full build + stage (runs PyInstaller, launcher, and the new apply-updater build)
powershell -ExecutionPolicy Bypass -File tools\stage_release.ps1 -Version 1.5.3

# 2. portable bootstrap zip (needs the Inno Setup .exe to exist first)
powershell -ExecutionPolicy Bypass -File tools\build_update_bootstrap.ps1 -Version 1.5.3
```

Notes for whoever runs this:
- `tools/build_update_repair.ps1` has **hardcoded defaults** for `-PackageUrl` and
  `-PackageSha256` pointing at the v1.5.3 zip. The SHA must be updated to the real published
  artifact's digest, or passed explicitly.
- `installer/ClicknTranslate.iss` builds the Setup executable (Inno Setup, not run here).
- Publishing to GitHub releases has **not** been done and needs the maintainer's credentials.
