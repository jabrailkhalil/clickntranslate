# Show HN draft

## Submission title

Show HN: Click'n'Translate – open-source screen OCR and translation by hotkey

## Link

Preferred: a dedicated page with an immediate download and source-code link.

Fallback: https://github.com/jabrailkhalil/clickntranslate

## First comment

Hi HN, I built Click'n'Translate, a GPL-3.0 desktop app for text that is visible
but difficult to copy or understand: games, videos, images, remote desktops, and
older interfaces.

The shortest workflow is: press a global hotkey, draw a region, and either copy
the OCR result or translate it. The same app can translate the full screen,
translate or replace selected text in another application, monitor several
changing regions, and open documents side by side.

The part I underestimated was state rather than OCR. Screen selection, overlays,
clipboard restoration, asynchronous OCR, translation, and persistent per-mode
language pairs can all outlive the action that created them. I ended up adding a
small UI-independent coordinator: only one interactive screen mode owns the
desktop at a time, the same hotkey toggles that mode off, and a different hotkey
stops the old owner before starting the new one. Worker results also carry a
session identity so stale responses can be ignored.

The OCR layer is deliberately replaceable: Windows OCR, Tesseract, RapidOCR,
and EasyOCR are supported. Translation can use an online provider or optional
local Argos Translate/Hy-MT packages. I keep the distinction explicit: OCR is
local; local translation stays on the machine; an online provider receives the
text the user asks it to translate.

The project has Windows and Linux downloads, no signup, and more than 700
automated checks in the current repository. I am especially looking for feedback
on the desktop architecture, difficult OCR inputs, Linux packaging, and the
trade-off between a small base download and optional engine packages.

Source and downloads:
https://github.com/jabrailkhalil/clickntranslate

One known rough edge: Windows binaries are not code-signed yet, and generic
heuristic antivirus warnings can occur because the app combines global hotkeys,
screen capture, clipboard access, optional autostart, and updating. Hashes and
source are public, and reports are investigated and submitted to vendors.

## Likely technical questions

**Why not use one OCR engine?**

Because the input is uncontrolled. Script, font, antialiasing, scaling,
background, and compression can change the best choice. Windows OCR is convenient
and light, Tesseract has broad language data, and the neural engines cover other
cases at the cost of heavier dependencies.

**Why a desktop app instead of a browser extension?**

The target text may be in any native application, game, video, or remote desktop.
A system-wide capture/hotkey workflow is the common layer. It also makes local
OCR and local translation packages possible without sending screenshots to a
web service.

**Why not continuously OCR the entire screen?**

I tried the broad idea and found it visually unstable: unrelated labels compete,
bounding boxes jump, and overlays can contaminate the next capture. The current
Dynamic mode asks users to select one or several meaningful regions, skips
unchanged frames, and updates only those overlays.

**How do you prevent an old worker from overwriting a new mode?**

Interactive modes have a single owner, and OCR work is associated with a session.
When a mode ends or another starts, late results no longer match the current
session and are discarded.

**What is sent over the network?**

Online translation sends the requested recognized/selected text to the chosen
provider. OCR itself is local. Argos Translate and Hy-MT are local after the
required model is installed. Update checks and requested package downloads also
use the network.

## Posting notes

- Submit the mature project, not “version 1.7.0 is released.”
- Keep the repo/download immediately usable without registration.
- Be available to answer questions for the next several hours.
- Do not ask anyone to upvote or seed comments.
- If a dedicated landing page contains only marketing, link directly to GitHub
  instead; Show HN is for something people can try.
