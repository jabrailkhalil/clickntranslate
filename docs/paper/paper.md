---
title: "Click'n'Translate: A reproducible desktop substrate for screen-text OCR and multilingual interface research"
tags:
  - Python
  - optical character recognition
  - screen text
  - machine translation
  - accessibility
authors:
  - name: Dzhabrail Elnurovich Khalilov
    orcid: 0009-0002-2391-692X
    affiliation: 1
    corresponding: true
affiliations:
  - name: Independent Researcher, Russian Federation
    index: 1
date: 15 August 2026
bibliography: paper.bib
---

# Summary

Click'n'Translate is a cross-platform desktop application for acquiring text
that cannot be selected directly in a graphical user interface. A user can
capture a region or complete screen, recognize text with one of several local
optical character recognition (OCR) engines, copy the result, or translate it
through an explicitly selected local or network-backed route. The application
also supports selected-text and document translation, language-package
management, versioned desktop releases, and configurable hotkeys.

For research, Click'n'Translate provides a concrete and versioned software
substrate between pixels, OCR engines, and translation services. An experiment
can pin a commit, preserve effective engine and language settings, and attach a
separate outcome-blind harness without treating the interactive application as
ground truth. This separation allows researchers to study screen-text
recognition, multilingual interface accessibility, fallback policies, and
local-versus-online processing while reporting exactly which behavior was
shipped and which behavior was introduced only for the experiment.

# Statement of need

Screen text differs from conventional scanned-document OCR. Strings are often
short, anti-aliased, scaled, overlaid on textured backgrounds, and embedded in
applications that do not expose an accessibility or selection interface.
General OCR engines can process an image, but a reproducible study also needs a
capture path, language configuration, image variants, package identities,
failure handling, and preserved provenance. Rebuilding those integration layers
for each experiment obscures the software condition and makes cross-platform
replication difficult.

Click'n'Translate addresses that integration problem for researchers and
practitioners studying screen text. It exposes Windows OCR, Tesseract
[@smith2007tesseract], RapidOCR, and EasyOCR as replaceable local backends and
supports offline translation through Argos Translate in addition to declared
online services. Optional engines and language packages are installed
separately, so a study can report the effective configuration rather than
silently inheriting every available model. The same public repository contains
the runtime, packaging definitions, platform adapters, tests, and release
history needed to identify the software condition.

# State of the field

Tesseract is a mature OCR engine with a documented recognition architecture
[@smith2007tesseract], while EasyOCR and RapidOCR provide neural inference
pipelines through reusable libraries [@easyocr; @rapidocr]. These projects focus
on recognition APIs rather than the complete desktop workflow from an arbitrary
screen region to a user-visible, optionally translated result. Scene-text
research has also shown that inconsistent training and evaluation choices can
make OCR comparisons misleading [@baek2019comparison], motivating explicit
configuration and provenance at the application boundary.

NormCap combines screen capture with OCR for copying otherwise inaccessible
text [@normcap], and Crow Translate integrates desktop translation with OCR and
global shortcuts [@crowtranslate]. Click'n'Translate differs in the combination
of four selectable OCR families, local and online translation routes, managed
language packages, area and full-screen overlays, selected-text replacement,
document translation, Windows and Linux platform adapters, and release-level
verification. Its research contribution is not a claim that each individual
component is new. It is a testable integration boundary and a documented method
for freezing that boundary in screen-text studies.

# Software design

The application separates interface orchestration from engine and platform
adapters. Capture backends normalize Windows and Linux desktop behavior before
OCR. Dedicated OCR and Argos worker processes isolate optional native and model
runtimes from the Qt interface. Engine discovery reports installed capability
rather than assuming that a configured language or model exists. Translation
routes are explicit, and local history is optional.

This architecture reflects three trade-offs. First, multiple backends increase
coverage but make native confidence values and language support incomparable;
the runtime therefore preserves engine identity instead of presenting one
confidence scale as universal. Second, bundling every model would make releases
large and difficult to audit, so optional packages are managed independently.
Third, desktop capture differs across operating systems and display servers, so
platform behavior is contained behind adapters and covered by deterministic
tests where native execution is unavailable.

Versioned PyInstaller builds, release checksums, installer and portable layouts,
and an automated regression suite cover application behavior independently of
any paper's statistical analysis. The research-use documentation specifies what
an experiment must additionally freeze: commit, operating system, display
configuration, engine packages, effective settings, artifact hashes, endpoints,
and label-opening chronology. The application source is released under the GNU
General Public License v3.0; independently distributed engines, models, and
libraries retain their upstream licenses.

# Research impact statement

A frozen Click'n'Translate snapshot at commit
`298521b11103a497ba0fe58ef297d7e4eea973c6` is the product substrate for the
CXT-Select methods study [@khalilov2026cxt]. That study formalizes the shipped
OCR candidate-ranking heuristic, distinguishes it from a separately calibrated
research selector, and provides an executable protocol and checksum-verifiable
development artifact. This is realized internal research use: the public
application behavior is traced to immutable source, while experiment-specific
selection, labels, and inference remain in a separate artifact.

The repository also provides sustained public development, tagged releases,
public issue and pull-request interaction, cross-platform packaging, and a large
regression suite. These signals establish that the software is maintained and
inspectable; they are not presented as evidence of independent scholarly
adoption. The research-use guide is intended to make such adoption auditable by
requiring future studies to cite an immutable version and disclose deviations.

# AI usage disclosure

OpenAI Codex and ChatGPT, including GPT-5-family coding models, and Anthropic
Claude Opus 5 Max were used during portions of implementation review, regression
test scaffolding, documentation editing, translation, and preparation of this
paper and the related CXT-Select manuscript. The author made the architecture,
release, and scientific decisions; reviewed and edited AI-assisted output;
verified references and numerical claims against source artifacts; ran the
automated and release tests; and accepts full responsibility for the software
and paper. AI systems are not listed as authors and were not used to fabricate
users, adoption, measurements, or citations.

# Acknowledgements

No external funding was received for this work. Click'n'Translate integrates
independent open-source OCR and translation projects; their authors and licenses
remain associated with those upstream components.

# References
