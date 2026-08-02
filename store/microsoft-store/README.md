# Microsoft Store release kit — 1.4.6

This folder contains the copy, policy notes, and submission checklist for the first Microsoft Store release of Click'n'Translate. The package itself is produced by `tools/build_msix.ps1` and written to the ignored `releases` directory.

## Before the final Store build

1. Create an Individual or Company developer account in Partner Center.
2. Create a new **MSIX or PWA app** and reserve `Click'n'Translate`.
3. Open **Product management → Product identity** and copy the exact **Package/Identity/Name** and **Package/Identity/Publisher** values.
4. Build the upload package with those values:

```powershell
.\tools\build_msix.ps1 `
  -Store `
  -IdentityName "VALUE_FROM_PARTNER_CENTER" `
  -Publisher "VALUE_FROM_PARTNER_CENTER"
```

Upload `releases/ClicknTranslate-1.4.6.0-store-x64.msixupload`. Do not upload the test package: its identity is intentionally different from the Store identity.

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

- 183 automated tests plus 8 packaging subtests pass.
- MakeAppx semantic package validation passes.
- The Windows App Certification Kit 10.0.26100 reports **OVERALL_RESULT=PASS**: 23 checks pass and one optional blocked-executable heuristic reports the expected worker/process-launch APIs documented in `certification-notes.md`.
- The built main executable contains the Per-Monitor V2 DPI and `asInvoker` manifest.
- The packaged Argos worker starts successfully in forced Store mode and creates its package data under LocalState.
- The `.msixupload` contains the exact MSIX payload verified by SHA-256.

Local sideload installation was not completed on the build PC because Developer Mode/sideloading is disabled and Windows requires interactive trust confirmation for a temporary self-signed root. The temporary certificate was removed. Partner Center's real identity and Store signing are still required for the final installable package.

The existing EXE installer is not a good first Store submission because it and its bundled PE files are not code-signed. MSIX is the intended Store channel; Microsoft provides final Store signing and managed updates after certification.
