# Microsoft Store release kit — 1.4.6

This folder contains the copy, policy notes, and submission checklist for the first Microsoft Store release of Click'n'Translate. The package itself is produced by `tools/build_msix.ps1` and written to the ignored `releases` directory.

## Partner Center identity

- Store ID: `9PG7PR6LTC6M`
- Store URL: `https://apps.microsoft.com/detail/9PG7PR6LTC6M`
- Package identity name: `Jabrail.ClicknTranslate`
- Publisher: `CN=563C277C-890B-44F4-AF41-691AE5E82D7B`
- Publisher display name: `Jabrail`
- Package family name: `Jabrail.ClicknTranslate_vedc6ewtdpt2c`
- Microsoft Entra application ID: `8c25c98d-4a30-43d8-980d-87688ed83168`

## Store build

Build the Store package with the exact Partner Center identity:

```powershell
.\tools\build_msix.ps1 `
  -Store `
  -IdentityName "Jabrail.ClicknTranslate" `
  -Publisher "CN=563C277C-890B-44F4-AF41-691AE5E82D7B" `
  -PublisherDisplayName "Jabrail"
```

Upload `releases/ClicknTranslate-1.4.6.0-store-x64.msixupload`. The accepted package contains version `1.4.6.0` for `x64`, targets Windows Desktop 10.0.17763.0 or later, and is 135,117,866 bytes. Do not upload the test package: its identity is intentionally different from the Store identity.

The exact MSIX payload is `releases/ClicknTranslate-1.4.6.0-store-x64.msix` (137,533,877 bytes) with SHA-256:

```text
32C4A2E71578A23A6FEF70C0411AF2D1AF2690E9F4EA254D48BD3597606789FE
```

## Prepared material

- Five localized listings: English, Russian, Simplified Chinese, Spanish, and French.
- MSIX visual assets generated from the existing application icon.
- Two real 1366 × 768 desktop screenshots in `assets/screenshots`, extracted from the supplied gameplay demo. They show the shipped translation-result window and meet the Store's minimum desktop dimensions.
- Marketing visuals and the animated GIF in `docs/images` remain available for GitHub and social promotion. Do not use them as proof-of-product screenshots in Partner Center.
- Privacy policy: `PRIVACY.md` in the repository root.
- Certification notes: `certification-notes.md` in this folder.

## Suggested Partner Center choices

- Price: Free
- Category: Productivity
- Subcategory: Utilities & tools
- Architecture: x64
- Minimum OS: Windows 10 version 1809 (build 17763)
- Markets: all markets where a free translation utility is permitted
- Age rating: answer the questionnaire factually; the app contains no built-in mature content
- Support URL: `https://github.com/jabrailkhalil/clickntranslate/issues`
- Privacy policy URL: `https://github.com/jabrailkhalil/clickntranslate/blob/main/PRIVACY.md`

## Package behavior

- Store builds write config, histories, OCR engines, and offline translation models to the package LocalState directory.
- The Update button opens Microsoft Store updates; it never attempts to overwrite the protected MSIX installation directory.
- “Start with OS” uses the declared `windows.startupTask` and is enabled only after the user checks the option.
- Portable and installer builds keep their existing data and GitHub updater behavior.

## Verification completed

- 184 automated tests plus 8 packaging subtests pass.
- MakeAppx semantic package validation passes.
- The Windows App Certification Kit 10.0.26100.7175 reports **OVERALL_RESULT=PASS** for the exact Store-identity package. The report is written to `build/msix/wack-report-store-3e2db216817645cbada5ed3d956f6cdb.xml`.
- The built main executable contains the Per-Monitor V2 DPI and `asInvoker` manifest.
- The packaged Argos worker starts successfully in forced Store mode and creates its package data under LocalState.
- The `.msixupload` contains the exact MSIX payload verified by SHA-256.
- Partner Center accepted and analyzed `ClicknTranslate-1.4.6.0-store-x64.msixupload` successfully. The declared `runFullTrust` capability is documented in the submission options and certification notes.

Local sideload installation was not completed on the build PC because Developer Mode/sideloading is disabled and Windows requires interactive trust confirmation for a temporary self-signed root. The temporary certificate was removed. Microsoft supplies the final Store signature after certification.

The existing EXE installer is not a good first Store submission because it and its bundled PE files are not code-signed. MSIX is the intended Store channel; Microsoft provides final Store signing and managed updates after certification.
