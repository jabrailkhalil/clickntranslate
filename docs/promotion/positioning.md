# Positioning and message guide

Facts reviewed **25 October 2026** against published 1.8.2 and the current README.
The upcoming update is planned in about two weeks and is not a public release yet.

## One-line positioning

**English**

Click’n’Translate is a free, open-source screen translator and OCR app for
Windows, macOS, Linux and Android, with online services and optional offline models.

**Russian**

Click’n’Translate — бесплатный экранный переводчик с открытым кодом для Windows,
macOS, Linux и Android: текст с экрана, онлайн-сервисы и офлайн-модели на выбор.

## The shortest useful pitch

Text is visible but cannot be selected? Capture it and read the translation.
On desktop, use a shortcut or the companion. On Android, use a floating button,
translate a photo, or type, paste and share text.

## Audience and workflows

- Players and readers: translate game dialogue, images, videos and applications.
- Language learners: compare a source with a translation or copy text for a dictionary.
- Desktop users: translate or replace selected text, edit common documents side by side,
  or follow several changing regions with Dynamic translation.
- Android users: translate over other apps, choose a capture region, process text
  or gallery images and return to local text history.
- Users with unreliable connections: install supported local recognition and
  translation models before going offline.

## Current facts

| Area | Published capability |
| --- | --- |
| Windows | Windows 10/11 x64; installer and portable ZIP |
| macOS | macOS 13.4+; separate Apple Silicon and Intel DMGs |
| Linux | x86_64 AppImage and portable tar.gz; capture/shortcuts depend on desktop session |
| Android | Android 8.0+ ARM64 APK; independent mobile app, no computer or root required for basic capture |
| Desktop interface | Eight languages: English, Russian, Spanish, German, French, Chinese, Portuguese and Italian |
| Translation catalog | 63 named desktop translation languages; actual recognition and translation coverage depends on engine/model |
| Android interface | English, Russian, German, French, Spanish and Chinese |
| Desktop OCR | Windows OCR or Apple Vision where available; Tesseract, RapidOCR, optional EasyOCR |
| Desktop translation | Online services; Argos Translate/Hy-MT after model installation; user-configured API services |
| Android translation | Online services, optional ML Kit offline models and user-configured API services |
| Licensing | Free, GPL-3.0-only; no required Click’n’Translate account or app advertising |

Desktop document formats: TXT, Markdown, DOCX, text-based PDF, HTML and RTF.
Desktop shortcuts, document editing and mobile permissions are separate workflows;
show the platform-specific recording instead of implying identical interfaces.

## Processing wording

> Local OCR processes images on the device. Offline translation works locally
> after supported models are downloaded. Online translation sends the requested
> text to the chosen service. If cloud OCR or an image-capable API is enabled,
> the selected image is sent too. Provider terms, limits and fees apply.

Desktop histories are optional and local. Android text history stores up to 50
entries locally and can be cleared. The website has its own privacy information
at https://clickn.dev/en/privacy/; do not extend an app-only privacy statement to
website analytics.

## Signing and first-launch wording

> Windows and macOS packages currently use the self-signed `jabrailkhalil`
> identity. This is not a publicly trusted Windows certificate or Apple Developer
> ID, and the Mac app is not notarized. SmartScreen or Gatekeeper may therefore
> warn on first launch. Use the official download and setup guide. Report an
> antivirus detection with its exact filename, version, hash and threat name.

Do not describe current desktop builds as unsigned, promise antivirus approval,
or claim that open source or a matching checksum proves a file harmless.

## Reusable descriptions

### Short

Free screen OCR and translation for Windows, macOS, Linux and Android.

### Directory description

Translate games, images and app text with Click’n’Translate. Free and open source
for Windows, macOS, Linux and Android; online services and offline models on demand.

### Russian short description

Бесплатный переводчик экрана для Windows, macOS, Linux и Android. Переводите игры,
изображения и текст приложений через онлайн-сервисы или установленные офлайн-модели.

## Voice and upcoming work

Use direct, specific language and disclose that the post is from the developer.
Preserve real personal experiences; do not invent benchmarks or a development story.
Describe the next update as planned in about two weeks, without an unannounced
version, fixed date or feature promise. Avoid evergreen download and test counts.
