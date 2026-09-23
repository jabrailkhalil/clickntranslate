# Windows 1.7.1: local release check, 2026-09-22

This records the earlier check of the September 19 ux5 artifact. A subsequent
[September 22 rebuild](LOCAL_1.7.1_QA_2026-09-22.md) is now the latest runnable
package; that rebuild also restored the local Python build environment.

## Latest runnable package

- Folder: `releases/ClicknTranslate-v1.7.1-win64-test-20260919-ux5/ClicknTranslate/`.
- Start `ClicknTranslate.exe` in that folder; retain its adjacent `app` directory.
- ZIP: `releases/Click-n-Translate-1.7.1-windows-portable-x64-test-20260919-ux5.zip`.
- ZIP size: 219186464 bytes.
- ZIP SHA-256: `4c51347ee4355748612728595d262f7de94d61024efbb49f5c76492981d76b08`.
- Launcher SHA-256: `04cf8fbf7ae1f720b4dc94a4a28c48c4562cd8d5ee874eac4ae209a9050ea939`.

This is the existing September 19 ux5 application with the recent UI, scaling,
assistant and translation changes. The September 22 changes affect release
verification scripts; the application was not rebuilt or published today.

## Checks performed today

- Compared frozen bytecode with the working source for 16 application modules:
  all matched, including `main`, settings, translation, assistant and UI modules.
- Verified all 4018 program files against the unpacked package manifest and
  independently verified every ZIP entry. No user data is included in the ZIP.
- Defender custom scans of both the package directory and final ZIP returned
  exit code 0 and explicitly reported no threats. Signature version:
  `1.459.333.0`, updated September 22 at 07:47 Moscow time.
- Real-time protection remained enabled. No exclusions or quarantine restores
  were used. Diagnostic scans preserve the inspected files.
- Extracted a separate clean copy of the ZIP, started its public launcher with
  an offscreen GUI and received the application's version-ready acknowledgement:
  `1.7.1`. Only the disposable smoke-test processes were stopped.
- All five project EXEs have file version `1.7.1.0` and remain unsigned.
- Release checks: **50 passed, 2 skipped**. The skipped integration checks need
  Windows SDK SignTool and Inno Setup, neither installed on this computer.

Local evidence is in `.tmp/defender-20260922/`: `ux5-package.json`,
`ux5-zip.json`, `ux5-signatures.json`, and `smoke/result.json`.
The package scan inventory includes local user-data filenames/hashes; do not
publish that private report as a public release asset. The ZIP report identifies
only the distributable archive.

## Reported false positive and release work

Today's Defender history records `Trojan:Win32/Wacatac.B!ml` against
`D:/Soft/system/ClicknTranslate/ClicknTranslate.exe` at 16:50 Moscow time.
That executable is now absent and Defender reports the detection inactive.
Its exact version/hash could not be recovered from the available event, so the
clean ux5 scan must not be presented as a vendor reclassification of that file.

The current build already uses folder-based PyInstaller packaging, disables UPX
and embeds version resources. The new `tools/scan_windows_release.ps1` records
Defender output and exact file hashes, requires enabled protection and recent
definitions, and rejects files changing during the scan. Signed staging and
signed installer creation invoke it automatically. Unsigned development stages
can opt in with `-ScanWithDefender`; final ZIPs can be checked separately.

Trusted signing still requires approval/configuration. SignPath requested
project reputation references on September 9, and the maintainer replied that
day. A Gmail search today found no later response. No messages or samples were
sent during this check.

For a recurring detection, submit the exact affected official EXE as a software
developer through [Microsoft's sample portal](https://www.microsoft.com/en-us/wdsi/filesubmission).
Microsoft documents this process in its [developer FAQ](https://learn.microsoft.com/en-us/defender-xdr/developer-faq).
Signing identifies the publisher and supports reputation; it does not guarantee
that every new binary immediately avoids [SmartScreen warnings](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

## Build environment

The copied `.venv` points to Python 3.12 under the old Windows account `admin`;
that interpreter does not exist here. Verification used an isolated official
Python 3.12.10 runtime in `.tmp/python-3.12.10-verify`, with the existing local
dependencies. Its download checksum and executable's trusted signature were
checked. No global Python installation or machine execution policy was changed.
Before rebuilding the application, restore a normal Python 3.12 build environment;
the available system Python 3.13 does not match the OCR runtime ABI requirement.
