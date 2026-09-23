# Product Hunt launch copy

This is a draft only. Product Hunt submission should point to a dedicated live
product page once it exists, not to this file.

## Name

Click'n'Translate

## Tagline

Translate any text on your screen with one hotkey

## Description (under 260 characters)

Free, open-source screen OCR and translation for Windows and Linux. Capture any
area, translate selected text or documents, replace text in place, or keep
multiple screen regions translated using online or offline engines.

## Topics

Suggested, subject to Product Hunt's available categories:

- Productivity
- Open Source
- Languages
- Accessibility
- Windows
- Linux

## Primary URL

Preferred: the dedicated product landing page.

Fallback: https://github.com/jabrailkhalil/clickntranslate

## First maker comment

Hi Product Hunt — I am Dzhabrail, the developer of Click'n'Translate.

I built it after getting tired of a very small but constant interruption: text
was right in front of me, but I could not select or understand it without taking
a screenshot and moving through several tools.

Click'n'Translate turns that into a hotkey. It can copy text from any screen
area with OCR, translate a selected area or the full screen, translate or replace
highlighted text, follow several changing regions, and open documents in a
side-by-side workspace.

I did not want to force one engine on everyone. Users can choose between Windows
OCR, Tesseract, RapidOCR, and EasyOCR. They can use convenient online
translation, or install Argos Translate/Hy-MT packages for local translation.
The privacy boundary is visible: online providers receive the text you ask them
to translate; local engines keep it on the computer.

The project is GPL-3.0, has no account, ads, developer analytics, or paid tier,
and has passed 1,000 downloads. I intend to keep it free.

Version 1.7.0 is the point where the app became a coherent set of workflows
rather than a collection of OCR buttons: modes now stop each other cleanly,
language pairs persist per mode, Dynamic translation supports several selected
areas, settings can be transferred safely, and bug reports exclude user text.

I would love feedback on two things:

1. Which workflow is immediately clear from the page, and which still needs an
   explanation?
2. Which languages, fonts, games, or desktop environments should I test next?

Thank you for taking a look. I will be here throughout the launch to answer
questions and investigate reproducible problems.

## Real GIF gallery order

1. `gifs/01-game-translation.gif` — **Translate game text without leaving the game.**
2. `gifs/02-area-ocr.gif` — **Copy text from any screen area with OCR.**
3. `gifs/03-selected-text.gif` — **Translate selected text in any application.**
4. `gifs/04-fullscreen-translation.gif` — **Translate the full screen with one hotkey.**
5. `gifs/05-in-app-update.gif` — **Download and install updates inside the app.**

These are real recordings already used by the project. Do not substitute the
generated gallery cards or the synthetic video draft. Product Hunt currently
documents a 3 MB limit for animated thumbnails; all five files fit that limit.
The form requires at least two gallery items before the gallery becomes visible.

## Launch-day replies

**Does it work offline?**

Yes, after installing the OCR data and an Argos Translate or Hy-MT package for
the language direction you need. Online providers remain available when speed
and convenience matter more.

**What data leaves the computer?**

OCR is local. With Argos/Hy-MT, translation is local too. If you select Google,
MyMemory, Lingva, or LibreTranslate, the requested text is sent to that provider.
Optional histories stay on the computer.

**Why so many OCR engines?**

Screen text varies enormously by script, font, scaling, background, and image
quality. The fastest or most accurate choice for one screen can be poor for
another, so the app lets users install only what they need.

**Why does an antivirus sometimes warn?**

The app uses global hotkeys, screen capture, clipboard integration, autostart,
and update behavior, and the Windows build is currently unsigned. Those factors
can trigger generic heuristic detections. Source and hashes are public, and
samples are submitted to vendors; new detections are still investigated rather
than automatically dismissed.

## Final checklist

- Personal Product Hunt account is eligible to post.
- Dedicated product URL is live and downloads work without signup.
- Tagline and description fit the current form limits.
- Five real application GIFs reviewed and ordered.
- No generated screenshots, mock UI, or synthetic video attached.
- Maker profile is attached.
- First comment is final and personal.
- Privacy and antivirus answers match the repository.
- No request for upvotes; invite honest feedback instead.
