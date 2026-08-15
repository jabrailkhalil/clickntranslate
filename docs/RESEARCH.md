# Research use

Click'n'Translate is an interactive software system, not a benchmark by itself.
Researchers can use a frozen release as a controlled screen-capture, OCR, and
translation substrate, while keeping study-specific sampling, labels, metrics,
and inference in a separate artifact.

## Suitable workflows

- Compare local OCR engines on the same screen regions and language settings.
- Study multilingual access to otherwise non-selectable interface text.
- Evaluate local and online translation routes under declared privacy and
  connectivity constraints.
- Reproduce platform behavior across Windows and Linux capture backends.
- Prototype selective prediction, fallback, or abstention policies over
  preserved OCR candidates.

The application does not provide a ground-truth corpus or establish that one
engine is universally better. A study must define its population, sampling unit,
labels, primary metric, exclusion rules, statistical analysis, and limitations.

## Freeze the software substrate

Record the following before collecting outcomes:

1. Git commit and release tag.
2. Operating system, display server, scaling, locale, and Python version.
3. Installed OCR and translation engines, package versions, model files, and
   language capabilities.
4. Effective Click'n'Translate settings with secrets and private histories
   removed.
5. Cryptographic hashes of the application artifact and experiment harness.
6. Whether network-backed translation was enabled and which endpoint was used.

The CXT-Select protocol uses commit
`298521b11103a497ba0fe58ef297d7e4eea973c6` as its frozen product snapshot. A
different commit is a different software condition and must be declared.

## Preserve observations

Store source identifiers separately from labels. Preserve raw candidate text,
engine identity, native confidence when available, image-variant identity,
timing measurements, errors, and abstentions before computing aggregate
statistics. Hash manifests and raw outputs before opening held-out labels.

Do not collect private screen content without authorization. Crop only the
minimum required region, redact identifiers, and document whether a source is
synthetic, public, licensed, or collected with consent.

## Reproduce the application tests

Install dependencies for the target platform and run:

```text
python -m pytest -q
```

The suite covers platform selection, OCR adapters, language-package management,
translation routing, document workflows, packaging, updates, localization, and
interface invariants. Native-engine and release smoke tests remain separate from
statistical evaluation of OCR quality.

## Cite and disclose

Use `CITATION.cff` for software metadata and cite the immutable release or commit
used. If a paper changes the application's selection logic or evaluates a new
research method implemented only in an external harness, distinguish that method
from the behavior shipped in the cited software snapshot.
