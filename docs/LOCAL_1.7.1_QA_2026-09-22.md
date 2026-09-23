# Private Windows rebuild 1.7.1 — September 22, 2026

Rebuilt the current working tree, including its uncommitted UI, assistant and
translation changes. No application source changes, commit, tag, push or public
release were made during this rebuild.

## Ready to use

- EXE: `releases/ClicknTranslate-v1.7.1-win64-test-20260922/ClicknTranslate/ClicknTranslate.exe`
- ZIP: `releases/Click-n-Translate-1.7.1-windows-portable-x64-test-20260922.zip`
- ZIP size: **215000667 bytes**.
- SHA-256: `af46ef54106e009e2cb906ebde8849efd5fcb5249cc1635f8d14d291289a198b`.
- App version: **1.7.1**, Windows file version **1.7.1.0**. Unsigned private build.

The runnable folder contains a verified copy of the latest ux5 user data.
The original data and all older release folders are preserved. The ZIP contains
program files only, with no portable user-data directory.

## Verification

- Full PyInstaller clean rebuild, plus freshly compiled launcher and updater.
- Embedded-archive verification passed for all three Python executables.
- Compared current-source bytecode in each executable: 51 local modules in the
  application, 52 in ArgosWorker, and 2 in OcrWorker; all matched.
- Verified all **4022** program files against the package manifest and then
  checked every ZIP entry against the corresponding staged file.
- Started the public launcher with an offscreen GUI; the application returned
  the GUI-ready acknowledgement for **1.7.1**. Test processes were stopped.
- The frozen RapidOCR worker recognized **HELLO WORLD / 12345** from a generated
  image. The frozen Argos worker passed its availability probe; this check did
  not download or install translation models.
- Defender scanned the complete clean stage and final ZIP, reported no threats
  and returned exit code 0. Real-time protection remained enabled.
- Copied four user-data files from ux5; source and destination hashes match.
  The final program manifest still passes after copying user data.

Signature and Defender reports are beside the staged `ClicknTranslate` folder.
Build, dependency, source-status, worker and GUI evidence is in
`.tmp/rebuild-20260922/`. The application test suite was not repeated: application
source is unchanged from the already tested ux5, and this run exercises the
newly frozen runtime and archive.

## Restored local build environment

The migrated `.venv` referred to the absent old Windows account's Python.
Restored it using the official Python **3.12.10** NuGet build distribution in
`.tmp/python-3.12.10-build/tools`; the Python executable's trusted signature was
verified. Existing dependency versions were retained. `.venv/Scripts/python.exe`
now works normally. Keep this local runtime directory while using this venv.
No system Python installation, PATH change or machine execution-policy change
was needed. Four Windows API-set DLLs are newly collected from this machine;
no program files from the prior package were removed.
