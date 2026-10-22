# Permanent release identities

Use these existing identities for updates. Do not generate replacement keys.
This repository contains public certificates and fingerprints only.

| Platform | Identity | Public fingerprint | Private material |
| --- | --- | --- | --- |
| Windows | jabrailkhalil, Authenticode | SHA-1 `A0888D5CDEF8AED02740B5AF0EE34D1A1D7A535C` | Nonexportable key in the signing Windows user's certificate store |
| macOS | jabrailkhalil, existing self-signed certificate | SHA-1 `FC6752F0026D34E5B63433544AF788B8FC1899EF` | Existing Mac signing keychain; encrypted copy in Actions secrets |
| OpenPGP | jabrailkhalil | `22873EED9E329E51D7D3EAE09A508E7BEF2D4205` | Existing signing Linux VM's private GnuPG directory |
| Android | CN=ClicknTranslate, OU=Android, O=ClicknTranslate; RSA-4096 | SHA-256 `1746bfc27cbbb823021ce32c1e7a2640584393d058b85e3d784711954bcafe85` | Original Android build computer; not supplied to the desktop builder |

The first Android release is the already signed `dev.clickn.translate` APK,
version 1.8.2, versionCode 7, arm64-v8a. APK Signature Scheme v2 verifies.
Its public certificate and APK-bound record are stored under
`tools/packaging/android/`. A separate public copy is retained outside Git at
`~/.android/clickntranslate-release-identities/2026-10-22/` on the desktop builder.
This is a public identity record, not a backup of the private Android keystore.
Future Android builds must use the same original key; the desktop release does
not re-sign or modify this APK.

Windows and Mac use the same existing self-signed identities as previous
releases. These signatures do not imply a publicly trusted CA, Apple Developer
ID, notarization or SmartScreen reputation. Verification files accompanying
each release contain the public identities and signed package checksums.
