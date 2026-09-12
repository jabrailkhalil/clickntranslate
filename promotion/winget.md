# WinGet package submission draft

This document prepares a future submission for the existing v1.7.0 installer.
It does not submit anything to `microsoft/winget-pkgs`.

## Recommended identity

| Field | Value |
| --- | --- |
| PackageIdentifier | `JabrailDigital.ClicknTranslate` |
| PackageVersion | `1.7.0` |
| PackageLocale | `en-US` |
| Publisher | `Jabrail Digital` |
| PackageName | `Click'n'Translate` |
| License | `GPL-3.0-only` |
| LicenseUrl | `https://github.com/jabrailkhalil/clickntranslate/blob/v1.7.0/LICENSE` |
| PublisherUrl | `https://github.com/jabrailkhalil` |
| PublisherSupportUrl | `https://github.com/jabrailkhalil/clickntranslate/issues` |
| PackageUrl | `https://github.com/jabrailkhalil/clickntranslate` |
| ReleaseNotesUrl | `https://github.com/jabrailkhalil/clickntranslate/releases/tag/v1.7.0` |
| InstallerType | `inno` |
| Scope | `user` |
| Architecture | `x64` |

Check that `JabrailDigital.ClicknTranslate` is still unused before submission.
Package identifiers are permanent enough that changing the spelling later is
undesirable.

## Installer

**Stable URL**

https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.7.0/Click-n-Translate-1.7.0-windows-x64-installer.exe

**SHA-256 published with v1.7.0**

`d4e51ee46ff2222418ade8fd3934ea7dbe09fa8744ef4c7d874bf4660da2e8cd`

Re-download the asset and independently calculate its hash immediately before
creating the PR. Do not copy the value into a manifest without verification.

## English metadata

**ShortDescription**

Extract and translate text from any screen area, selection, or document.

**Description**

Click'n'Translate is a free, open-source desktop screen OCR and translation
application. It can copy text from a selected region, translate a region or full
screen, translate or replace selected text, monitor multiple changing screen
regions, and translate common document formats. It supports configurable global
hotkeys, multiple OCR engines, and online or optional offline translation.

**Tags**

- translation
- translator
- ocr
- screen-capture
- image-to-text
- offline
- productivity
- accessibility

## Candidate manifests

Use WinGetCreate where possible so the current schema is generated instead of
copying a stale template:

```powershell
winget install wingetcreate
wingetcreate new "https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.7.0/Click-n-Translate-1.7.0-windows-x64-installer.exe"
```

Expected file set under the identifier/version path:

```text
manifests/j/JabrailDigital/ClicknTranslate/1.7.0/
  JabrailDigital.ClicknTranslate.yaml
  JabrailDigital.ClicknTranslate.installer.yaml
  JabrailDigital.ClicknTranslate.locale.en-US.yaml
```

Likely installer-manifest facts to verify from the generated output:

```yaml
PackageIdentifier: JabrailDigital.ClicknTranslate
PackageVersion: 1.7.0
InstallerType: inno
Scope: user
Installers:
  - Architecture: x64
    InstallerUrl: https://github.com/jabrailkhalil/clickntranslate/releases/download/v1.7.0/Click-n-Translate-1.7.0-windows-x64-installer.exe
    InstallerSha256: D4E51EE46FF2222418ADE8FD3934EA7DBE09FA8744EF4C7D874BF4660DA2E8CD
ManifestType: installer
```

Do not paste this fragment as a complete manifest. WinGet schemas and required
fields can change, and WinGetCreate should supply the current version.

## Pre-submission checks

1. Confirm the public GitHub asset downloads without authentication or a
   short-lived URL.
2. Calculate SHA-256 locally and compare it with the release notes.
3. Install silently in a clean Windows Sandbox and confirm the main executable
   exists at `%LOCALAPPDATA%\Programs\ClicknTranslate`.
4. Launch the installed app, close it, and uninstall it.
5. Confirm uninstall removes application files without removing unrelated user
   data.
6. Run `winget validate <manifest-directory>`.
7. Run the `winget-pkgs` SandboxTest script against the manifest directory.
8. Review current `winget-pkgs` policies, especially malware scanning and
   installer behavior.
9. Resolve or document antivirus detections before submission. A WinGet PR is
   automatically scanned and may be rejected even when the software is benign.
10. Submit through a fork/PR and respond to validation comments without changing
    the binary behind the versioned URL.

## Update process for later releases

For each new version, keep the same `PackageIdentifier`, update versioned URLs
and hashes, validate in Sandbox, and submit a new version directory. Never reuse
or replace a release asset at an old immutable URL after its manifest is merged.
