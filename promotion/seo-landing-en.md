# English SEO landing page copy

## Metadata

**Suggested slug:** `/screen-translator/`

**Title:** Free Screen Translator for Windows | Click'n'Translate

**Meta description:** Copy or translate text from games, images, videos, apps,
and documents. Free open-source screen OCR with hotkeys and online or offline
engines.

**Canonical:** `[PUBLIC_LANDING_URL]/screen-translator/`

**Open Graph title:** Translate any text on your screen with one hotkey

**Open Graph description:** Free, open-source screen OCR and translation for
Windows and Linux — including selected text, documents, full-screen, and live
multi-area translation.

## Hero

### Eyebrow

Free and open source · Windows and Linux · No account

# Translate any text on your screen

Copy text that cannot be selected. Translate a game, image, video, application,
or document. Replace highlighted text in place or keep several screen regions
translated as they change — all with configurable hotkeys.

**Primary CTA:** Download for Windows

**Secondary CTA:** View source on GitHub

**Tertiary links:** Portable ZIP · Linux downloads · Release notes

Microcopy below CTA:

> Latest release: detected automatically from GitHub. Free under GPL-3.0. No account, ads, or
> developer-operated analytics.

## Demo caption

Select one or several important regions. Click'n'Translate recognizes the text
locally and updates translated overlays when it changes.

## Problem section

## Stop retyping text you can already see

Some text refuses to behave like text. It is trapped inside a screenshot,
subtitle, game, remote desktop, video, scanned page, or old interface. Copying it
often means taking a screenshot and moving through several tools.

Click'n'Translate makes the screen itself the input. Press a hotkey, select what
matters, and continue where you were.

| You need to… | Use… | You get… |
| --- | --- | --- |
| Copy unselectable text | Area OCR | Recognized text in your clipboard |
| Translate part of the screen | OCR translation | A focused result window |
| Understand an interface | Full-screen translation | Translation over the original regions |
| Translate highlighted text | Selection translation | Your saved language pair |
| Write in another language | Selection replacement | Translated text in the same field |
| Follow subtitles or dialogue | Dynamic translation | Updating overlays over chosen regions |
| Translate a file | Document workspace | Original and translation side by side |

## Dynamic translation section

## Translate changing text without translating the entire desktop

Draw one or several regions around the text you care about. Dynamic translation
checks those regions at your chosen interval, skips unchanged frames, and
updates the overlays when the text changes. Press the same shortcut again to
stop.

You control refresh frequency, overlay opacity, whether the original remains
visible, and whether the mode pauses when its application is inactive.

**CTA:** See Dynamic translation on GitHub

## Engines section

## Use the engine that fits the screen

Different fonts, scripts, backgrounds, and image quality need different tools.
Click'n'Translate does not lock you into one OCR or translation route.

### OCR on your computer

- Windows OCR
- Tesseract
- RapidOCR
- EasyOCR

### Fast online translation

- Google
- MyMemory
- Lingva
- LibreTranslate

### Optional offline translation

- Argos Translate
- Hy-MT

Install only the language data and offline models you need from the built-in
package manager.

## Privacy section

## Know where your text goes

OCR runs locally. Argos Translate and Hy-MT also translate locally after their
packages are installed. If you choose an online provider, the text you request
to translate is sent to that provider. Copy and translation histories are local
and optional.

**CTA:** Read the privacy policy

## Documents section

## Screen translation when you need it, a workspace when you do not

Open `.txt`, `.md`, `.docx`, `.pdf`, `.html`, `.htm`, or `.rtf`. Work with the
original and translation side by side, translate a selection or complete text,
and save the result as text, Markdown, or a reopenable local session.

## Trust section

## Open code, visible trade-offs

- GPL-3.0 source code and public issue tracker.
- Versioned Windows and Linux downloads.
- SHA-256 hashes published with releases.
- More than 700 automated checks in the current repository.
- Privacy-safe diagnostic reports that exclude clipboard contents, documents,
  histories, credentials, and OCR logs.

### A note about Windows antivirus warnings

Click'n'Translate uses global hotkeys, screen capture, clipboard integration,
optional autostart, and updating. The Windows executable is currently unsigned,
so some heuristic scanners may show a generic warning. Release source and hashes
are public, and reported samples are submitted to antivirus vendors. New
detections are investigated; users should download only from the official
repository and report unexpected warnings.

## FAQ

### Is Click'n'Translate free?

Yes. It is open-source software distributed under GPL-3.0, with no account,
advertising, or paid tier.

### Does it work offline?

Yes, after installing the required OCR language data and an Argos Translate or
Hy-MT package. Online translation providers still require a connection.

### Can it translate games and videos?

Yes. OCR reads pixels from a selected region, so the source does not need to be
selectable. Results depend on the font, size, contrast, language data, and chosen
OCR engine.

### Does it support Linux?

Yes. The release page provides an x86_64 AppImage and a portable TAR archive.
Some desktop integration and capture behavior can depend on the Linux session.

### Can it replace selected text?

Yes. Highlight text in another application and use the replacement shortcut.
Click'n'Translate translates it with that mode's saved language pair and inserts
the result in place.

### Is text sent to the developer?

No developer-operated telemetry or history upload is built in. Online
translation text is sent to the provider the user selects. Optional histories
remain local.

## Final CTA

## See it. Select it. Understand it.

Download Click'n'Translate, press `Ctrl + Alt + T`, and translate the first piece
of screen text that gets in your way.

**Primary CTA:** Download the latest Click'n'Translate

**Secondary CTA:** Browse the source

**Support links:** Report a bug · Telegram · Privacy · License

## Structured data draft

Replace `[PUBLIC_LANDING_URL]` and verify every URL before deployment.

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Click'n'Translate",
  "applicationCategory": "UtilitiesApplication",
  "operatingSystem": "Windows 10, Windows 11, Linux",
  "isAccessibleForFree": true,
  "license": "https://github.com/jabrailkhalil/clickntranslate/blob/main/LICENSE",
  "url": "[PUBLIC_LANDING_URL]/screen-translator/",
  "downloadUrl": "https://github.com/jabrailkhalil/clickntranslate/releases/latest",
  "codeRepository": "https://github.com/jabrailkhalil/clickntranslate",
  "description": "Free open-source screen OCR and translation for Windows and Linux with configurable hotkeys and online or offline engines.",
  "author": {
    "@type": "Person",
    "name": "Dzhabrail Khalilov"
  },
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  }
}
```

Do not add ratings or review markup until genuine, visible reviews exist on the
page.
