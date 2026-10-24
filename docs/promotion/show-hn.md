# Show HN draft

Updated **25 October 2026** for published **1.8.2**. This file is not a submission.
Check for an existing story and the current Show HN guidelines. The next update
is planned in about two weeks; present something people can actually try.

## Title

Show HN: Click’n’Translate — open-source screen OCR for desktop and Android

## Link

https://translate.clickn.dev/

Source: https://github.com/jabrailkhalil/clickntranslate

## First-comment draft

Hi HN, I built Click’n’Translate, a GPL-3.0 screen OCR and translation app for
Windows, macOS, Linux and Android.

On desktop, the shortest flow is a shortcut, a selected region, and either
recognized text or a translation. The app also handles selected-text replacement,
full-screen overlays, changing regions and common documents. Android uses a
floating button over other apps and supports text, photos, sharing and local history.

The desktop architecture separates capture, OCR workers, translation and overlay
ownership. Mode/session identities prevent late worker results from updating a
new interaction. Native Windows OCR and Apple Vision are available on their
platforms, alongside Tesseract, RapidOCR and optional EasyOCR. Desktop offline
translation uses Argos Translate/Hy-MT; Android has supported ML Kit models.

Local engines process on the device; online translation sends text to the selected
provider, while an enabled cloud OCR or image API can send the selected image.
There is no required Click’n’Translate account. Model availability and capture
restrictions differ by platform.

I would value reproducible OCR samples and feedback on first launch, packaging,
accessibility and Linux integration. Dated validation reports are in the repository;
one platform check does not establish support for every environment.

## Technical replies

**Why several engines?** Script, font, scaling, contrast and layout affect the
result. Optional models and packages let users choose the trade-offs.

**Why an app?** The text may be inside a native app, game, video or remote desktop.
Desktop capture/shortcuts and Android’s consent-based floating workflow reach
those contexts. Protected content can still block capture.

**Offline?** Install supported models first. Online providers need internet and
receive the data required by the configured service.

**Signatures?** Windows and macOS use the existing self-signed `jabrailkhalil`
identity. The Mac app is not Apple-notarized. Setup guides explain first launch;
source and checksums do not make antivirus detections automatically false positives.

## Posting notes

Disclose the developer relationship, follow current Show HN rules and remain
available to answer. Do not ask friends to vote or seed comments. The upcoming
update is a plan, not an available download or fixed launch date.
