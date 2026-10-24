# Reddit drafts

Updated **25 October 2026** for published **1.8.2**. These are unsubmitted drafts.
Recheck each community’s live rules, flair, account requirements and developer
self-promotion policy immediately before use. Existing posts should be updated
rather than duplicated. Do not publish these back to back.

## 1. r/SideProject — workflow feedback

**Title:** I built an open-source screen translator for desktop and Android

**Body:**

I’m the developer of Click’n’Translate. I wanted a shorter route from text I could
see in a game or app to text I could actually read or copy.

On desktop, it captures regions or the full screen, translates or replaces
selected text, follows changing regions and opens common documents. A shortcut
or optional companion opens the actions. Android has its own floating screen
button plus text, photo, Share and local-history workflows.

It is free and GPL-3.0, with Windows, macOS, Linux and Android downloads.
Users choose online services or supported offline models. An online service
receives the required text; a configured image API can receive the selected image.

https://translate.clickn.dev/

I would appreciate first-launch feedback: which action would you try first,
and is it clear how to start? Reproducible OCR samples are useful too.

## 2. r/opensource — architecture and contributions

**Title:** Click’n’Translate: GPL screen OCR and translation on desktop and Android

**Body:**

I maintain Click’n’Translate, a free screen OCR and translation project. Desktop
uses platform-specific capture, replaceable OCR workers, per-mode language pairs
and overlays; Android provides a consent-based floating capture workflow along
with text and photo tools. Published builds cover Windows, macOS, Linux and Android.

Desktop local OCR includes Windows OCR/Apple Vision where available, Tesseract,
RapidOCR and optional EasyOCR. Argos Translate/Hy-MT support local translation
after installing models; Android offers supported ML Kit models. Online and
user-configured API services remain separate choices with their own data paths.

Code/build documentation: https://github.com/jabrailkhalil/clickntranslate
Product/downloads: https://translate.clickn.dev/

Useful contributions include privacy-safe OCR samples, Linux environment reports,
accessibility review and focused localization fixes. Please include the OS,
engine, source language and reproduction steps in bug reports.

## 3. Software community — practical utility

Use only where current rules allow a developer’s own free software.

**Title:** Free screen OCR and translation for Windows, macOS, Linux and Android

**Body:**

Disclosure: I’m the developer. Click’n’Translate copies or translates visible text
inside games, pictures and apps. Desktop provides shortcuts, selected-text
replacement, changing-region overlays and documents. Android uses a floating
button and supports photos, text and Share actions.

Local models are optional downloads. Online text/image services receive the data
required by the selected provider. Windows/macOS builds use a self-signed
`jabrailkhalil` identity, so first-launch warnings are explained in the setup guide;
an antivirus detection still needs investigation.

Downloads/setup: https://translate.clickn.dev/

## 4. Language-learning community — permitted resource thread

Use only in a current thread or format explicitly allowed by its rules.

I’m the developer of Click’n’Translate, a free open-source tool for reading text
inside games, images and apps. Desktop can compare original text with a
translation or copy recognized text for a dictionary; Android adds a floating
screen button, text and photo translation. Online services and supported offline
models are available, with engine-specific language coverage.

It is a lookup aid, not a substitute for checking context or learning the language.
Which workflow helps you more: a small result window, an overlay or copying the
original into your dictionary?

https://translate.clickn.dev/

## 5. GitHub community — permitted self-promotion thread

**Click’n’Translate** — free GPL screen OCR and translation for Windows, macOS,
Linux and Android. Desktop shortcuts, overlays and documents; Android floating
screen translation, photos and text. Online services and supported offline models.

Repository: https://github.com/jabrailkhalil/clickntranslate
Product: https://translate.clickn.dev/

Feedback on OCR, first launch, accessibility and packaging is welcome. GitHub
activity must use the owner’s `jabrailkhalil` account.

## Timing

Refresh existing entries now. The next update is planned in about two weeks;
announce its features only once verified and published. Stagger genuinely
different posts, answer substantive questions and never coordinate votes or pose
as an unrelated satisfied user.
