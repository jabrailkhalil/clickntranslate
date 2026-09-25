# Reddit campaign drafts

Do not publish these back to back and do not copy one draft into another
community. Re-check each community's current rules, required flair, account-age
requirements, and self-promotion policy immediately before posting. Always say
that you built the project.

## 1. r/SideProject — product and feedback angle

Suggested flair: `Self Promotion`, `I Made This`, or the closest current option.

**Title**

I kept leaving games and apps just to translate one line, so I built a hotkey-based screen translator

**Body**

I built Click'n'Translate because the normal workflow for text you cannot select
is absurd: screenshot, open a website, upload, OCR, copy, translate, switch back.

The app now handles a few different versions of that problem:

- select any screen area and copy its text with OCR;
- translate an area or the whole screen;
- translate highlighted text, or replace it with the translation;
- keep one or several chosen screen regions translated as their contents change;
- open common document formats in a side-by-side translation workspace.

It supports several OCR engines and both online and offline translation routes.
The offline packages are optional, so the main download does not include several
gigabytes of models. There is no account, paid plan, advertising, or analytics.

The hardest part was not calling an OCR library. It was making global hotkeys,
the clipboard, overlays, engine switching, language pairs, and mode cleanup
behave predictably together. I eventually added a single-owner coordinator so a
new screen mode always closes the previous one, while pressing the same hotkey
again stops it.

The project is GPL-3.0 and has Windows and Linux builds:
https://github.com/jabrailkhalil/clickntranslate

I would value specific feedback on the first-run experience: after opening the
README, can you tell which mode you would use first and why? I am also interested
in screen layouts or fonts that are difficult for its OCR.

## 2. r/opensource — engineering and contribution angle

**Title**

Click'n'Translate: a GPL screen OCR and translation app with interchangeable local engines

**Body**

I maintain Click'n'Translate, an open-source desktop utility for extracting and
translating text that is visible on screen but not necessarily selectable.

The project combines four OCR routes (Windows OCR, Tesseract, RapidOCR, and
EasyOCR), online translators, and optional local translation through Argos
Translate or Hy-MT. The important privacy distinction is explicit: OCR is local,
installed offline translators stay local, and text is sent to the selected
provider only when an online translator is used.

Recent work focused on the less glamorous parts of desktop software:

- mutually exclusive screen modes with toggle-off hotkeys;
- rejecting stale results from workers after a mode changes;
- optional histories and predictable clipboard restoration;
- language-package management without requiring a terminal;
- settings export that excludes histories, documents, credentials, and caches;
- a diagnostic archive that avoids user text;
- Windows and Linux release paths.

Source and build instructions:
https://github.com/jabrailkhalil/clickntranslate

The project is GPL-3.0. Useful contributions right now would be reproducible OCR
cases, Linux desktop-session reports, accessibility review, translations of the
interface/documentation, and small focused pull requests. If you test it, please
include the OS, OCR engine, source language, and a privacy-safe sample when
reporting a problem.

## 3. r/software or a Windows software community — practical utility angle

Post only if current rules permit developers to share their own free software.

**Title**

Free open-source utility for copying or translating text from any part of the screen

**Body**

Disclosure: I am the developer.

Click'n'Translate is for the awkward cases where text is visible but cannot be
selected: games, videos, images, remote desktops, and older applications. Press
a global hotkey, draw a region, and either copy the recognized text or translate
it. It can also translate highlighted text, replace a selected sentence in
place, translate a full screen, monitor several changing regions, and open
documents side by side.

You can choose Windows OCR, Tesseract, RapidOCR, or EasyOCR. Translation can use
an online provider, or run locally with an installed Argos/Hy-MT package. The app
has no account requirement, ads, or developer analytics.

Windows installer, portable build, Linux downloads, source, and SHA-256 files:
https://github.com/jabrailkhalil/clickntranslate/releases/latest

One honest warning: the Windows executable is not code-signed yet. Because the
app uses screen capture, global hotkeys, clipboard access, optional autostart,
and self-update behavior, some heuristic antivirus scanners can flag a build.
The source is public and I submit false-positive samples to vendors, but any new
detection should still be reported and investigated.

## 4. r/languagelearning — weekly self-promotion thread only

Use in the community's current self-promotion/resources thread, not as a
standalone submission unless its rules explicitly allow that.

**Comment**

I am building a free open-source tool called Click'n'Translate for learning from
text inside games, videos, images, and desktop apps.

The workflow I wanted was simple: keep reading, press a hotkey when I get stuck,
and compare the original with a translation without typing the sentence again.
It can translate one selected area, highlighted text, a full screen, or several
changing regions. It can also extract the original text to the clipboard, which
is useful for dictionaries and flashcards.

It supports different OCR engines because stylized fonts and scripts behave very
differently. Translation can be online, or local after downloading an Argos or
Hy-MT package. It is not a replacement for checking context or learning the
language; it is meant to remove the interruption between seeing a phrase and
looking it up.

Project and downloads: https://github.com/jabrailkhalil/clickntranslate

I would be interested in which reading workflow people prefer: a small result
window, translated overlays, or copying the original into their own dictionary.

## 5. r/github — recurring self-promotion megathread

Use only in the active official self-promotion megathread.

**Comment**

**Click'n'Translate** — GPL-3.0 desktop screen OCR and translation for Windows
and Linux.

Repository: https://github.com/jabrailkhalil/clickntranslate

It can extract text from any selected screen region, translate an area or the
whole screen, translate or replace selected text, monitor multiple changing
regions, and translate common document formats. Users can switch between four
OCR engines and online or optional offline translation providers. Global
hotkeys, language pairs, histories, and packages are configurable.

Current areas where feedback or contributions would help: Linux environment
coverage, OCR samples with difficult fonts, UI accessibility, translations, and
reproducible bug reports. The issue tracker is public, and the app can create a
privacy-safe diagnostic package that excludes clipboard contents, documents,
histories, and credentials.

## Posting rhythm

- Day 1: answer existing relevant discussions without linking unless the tool
  directly solves the question.
- Day 3: r/SideProject draft.
- Day 6 or later: r/opensource draft, with different screenshots and technical
  discussion.
- Next eligible weekly threads: r/languagelearning and r/github comments.
- Use the software-community post only after moderator rules are confirmed.

Reply to every substantive question. Do not delete criticism, argue about votes,
or pretend to be a user of your own product.
