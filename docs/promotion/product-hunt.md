# Product Hunt launch draft

Updated **25 October 2026**. Unsubmitted copy; confirm the current listing and
account eligibility before posting. The live product is **1.8.2**. A further
update is planned in about two weeks; choose the launch date after it is ready.
Recheck current requirements in `platform-rules.md`.

## Listing fields

**Name:** Click’n’Translate

**Tagline:** Screen translation for desktop and Android

**Description:** Free, open-source screen OCR and translation for Windows, macOS,
Linux and Android. Translate game and app text, capture regions, read images,
and choose online services or supported offline models.

**Product URL:** https://translate.clickn.dev/

**Source:** https://github.com/jabrailkhalil/clickntranslate

Suggested topics, if available: Productivity, Open Source, Languages.
Select no more than three, using the current form’s categories.

## Maker-comment draft

Hi Product Hunt — I’m Dzhabrail, the developer of Click’n’Translate.

I built it for text that is visible but cannot easily be selected or understood:
game dialogue, pictures, videos and application interfaces. On desktop, a shortcut
or the companion opens the action you need: copy text, translate a region or the
full screen, translate a selection, replace it, or follow changing regions.
A document workspace keeps original and translation side by side.

Android has its own workflow: a floating screen button, region capture, text and
photo translation, sharing and local text history. It runs on the phone without
requiring the desktop app.

The project is free and GPL-3.0. Local engines and downloaded offline models
process on the device. Online services receive the requested text; a cloud OCR
or image-capable API can receive the selected image when enabled. Service fees,
models and supported languages depend on the provider.

I would appreciate feedback on first launch, difficult OCR samples and which
screen-translation workflow you actually use. Please include the platform and
engine when reporting an issue. Thank you for trying it.

## Media and preparation

Use real workflow recordings from `gifs/` and current desktop/Android screenshots
from `../images/`. Some GIFs show older desktop windows; label them as workflow
demonstrations. Do not use unused generated gallery/video mockups. Recheck current
file-size, format and gallery requirements before upload.

Finalize the feature list against the actual public release, make downloads
immediately available, attach the developer’s own profile and reserve time to
answer. Do not solicit coordinated votes or post from another person’s account.
GitHub actions use only `jabrailkhalil`.

## Short answers

**Offline?** Desktop supports Argos Translate/Hy-MT; Android offers supported
ML Kit models. Download necessary models first. Online services need a connection.

**Mac/Windows warnings?** Packages use the self-signed `jabrailkhalil` identity.
The Mac app has no Apple Developer ID/notarization; Windows signing is not publicly
trusted CA signing. Follow the setup guide and investigate antivirus detections.

**Next update?** Planned in about two weeks as of 25 October. It is not released;
this draft does not promise a version, exact date or unverified feature.
