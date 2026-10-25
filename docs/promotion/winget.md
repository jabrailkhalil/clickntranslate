# WinGet package candidate

Prepared **25 October 2026** for the existing **1.8.2** Windows installer.
This is metadata preparation, not evidence of a submitted or accepted package.
Check current `microsoft/winget-pkgs` rules and existing identifiers before a PR.

## Candidate identity

| Field | Value |
| --- | --- |
| PackageIdentifier | `JabrailDigital.ClicknTranslate` — confirm availability |
| PackageVersion | `1.8.2` |
| PackageLocale | `en-US` |
| Publisher | `Jabrail Digital` |
| PackageName | `Click'n'Translate` |
| License | `GPL-3.0-only` |
| LicenseUrl | `https://github.com/jabrailkhalil/clickntranslate/blob/v1.8.2/LICENSE` |
| PublisherUrl | `https://clickn.dev/` |
| PublisherSupportUrl | `https://github.com/jabrailkhalil/clickntranslate/issues` |
| PackageUrl | `https://translate.clickn.dev/` |
| ReleaseNotesUrl | `https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.8.2` |
| InstallerType | Expected `inno`; confirm with WinGetCreate and the actual file |
| Scope / architecture | Expected user / x64; verify installer behavior |

Installer URL:

https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.8.2/Click-n-Translate-1.8.2-windows-x64-installer.exe

## Hash and manifest preparation

The obsolete 1.7.0 hash has been removed. Download the **exact current asset**,
calculate SHA-256 and compare it with its published checksum before preparing a
manifest. No hash is supplied here because this refresh did not download or
install the Windows package.

Use WinGetCreate to generate current-schema manifests, then review its detected
installer fields. Keep the permanent package identifier after the first accepted
submission. Use immutable versioned asset URLs; never replace an old binary in place.

Expected version directory:

`manifests/j/JabrailDigital/ClicknTranslate/1.8.2/`

## English metadata

**ShortDescription:** Extract and translate text from screen regions, selections and documents.

**Description:** Click’n’Translate is a free, open-source screen OCR and translation
application. The Windows edition provides area/full-screen capture, selected-text
translation and replacement, Dynamic translation, document workspaces, configurable
shortcuts, an optional companion and online/offline engine choices. The broader
project also provides macOS, Linux and Android editions.

Suggested tags: `translation`, `ocr`, `screen-capture`, `offline`, `productivity`.

## Before submitting

- Confirm the identifier is new or update the existing package rather than duplicating it.
- Recheck the current repository policies and generated manifest schema.
- Verify the downloaded asset, checksum, signature and detected installer metadata.
- Install, launch and uninstall in a clean Windows environment; check silent flags,
  installation path, AppId and preservation of user data.
- Run the current WinGet manifest validation and required sandbox checks.
- Investigate antivirus detections. A self-signed Authenticode certificate does not
  guarantee trust or acceptance by the package repository.
- Create a PR only through the owner’s authorized GitHub identity `jabrailkhalil`.

For the next update, wait until its public immutable installer and checksum exist,
then repeat the validation for that exact version. Do not create a future-version
manifest from a private test build or assume the planned release date is fixed.
