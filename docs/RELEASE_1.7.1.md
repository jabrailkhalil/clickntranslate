# Click'n'Translate 1.7.1 — draft

Status: source version prepared; not published. Windows artifacts have not yet
been signed with a trusted publisher certificate.

Local validation on 2026-09-05: the Windows release stage built successfully,
all three PyInstaller embedded archives passed integrity checks, and the frozen
GUI acknowledged startup as 1.7.1 using isolated test data. All five project EXEs
contain version 1.7.1.0 and the product name. The generated
`windows-signatures.json` records their hashes and `NotSigned` status. Windows
packaging/signing tests passed (28 tests); Linux-compatible packaging checks
passed (13 tests). These checks are not an antivirus verdict.

The subsequent full QA run rebuilt both Windows and Linux executables and
passed 799 Windows tests and 780 Linux tests. Additional checks cover fractional
display scaling, actual online/offline translation, OCR, frozen startup and
archive integrity. See [QA_1.7.1.md](QA_1.7.1.md) for exact coverage, fixes and
remaining external/manual checks.

Main-window scaling was added after those frozen builds. Its initial version
passed the full Windows/Linux suites (811/792 tests). The final control uses
left/right arrows and an editable percentage, with each size applied in one
update. The current UI validation is recorded in the scaling notes below.
The final release artifacts still need to be rebuilt from this updated source.
See [UI_SCALING.md](UI_SCALING.md) for behavior and validation details.

## Changes

- Clearer main-window sections, space between language selection and text input,
  separate shortcut settings and reference rows, and a visible long-text expand action.
- Settings tabs integrated into the title panel, consistent buttons across windows,
  and readable borders and controls in dark and light themes.
- An aligned interface-scale field in General settings: type an exact percentage
  or use 5% arrow steps. Repeated clicks keep the arrow under the pointer.
  Text, icons and spacing scale together, with persistence and a monitor-size limit.
- Keep the window's exposed background in the selected theme while resizing.
- A 28-step setup guide with a separate count of recommended settings that are ready.
- Layout checks for the fixed window across six interface languages on Windows and Linux.
- Linux startup and single-instance reliability improvements; see
  [the implementation notes](LINUX_IPC_RELIABILITY.md).
- Preserve the Linux listener's BUSY reply when it closes before the client writes.
- Split long MyMemory input within the provider's UTF-8 byte limit and translate
  paths/URLs through Lingva's GraphQL endpoint to avoid REST routing failures.
- Keep words on the same OCR line in reading order, including slightly tilted boxes.
- Stronger light-theme main-window outlines at fractional display scaling.
- Require the final portable archive's checksum when building the update-repair helper.
- Windows version and publisher resources for the application and both frozen workers.
- macOS source support for Apple Silicon and Intel: native Vision OCR, hotkeys,
  permissions, Retina capture, login startup and separate native bundle builds.
  Native acceptance is pending; see [MACOS_HANDOFF.md](MACOS_HANDOFF.md).
- Keep the selected OCR and translation engines in every mode, reporting failures
  without silently switching to a different provider or local translator.
- An explicit signing and verification step for the launcher, application, OCR and
  translation workers, updater, installer and embedded uninstaller. This is build
  infrastructure; it does not mean the artifacts already have signatures.

## Before publication

Build and check the final Windows and Linux artifacts. Complete trusted signing
using [WINDOWS_SIGNING.md](WINDOWS_SIGNING.md), publish SHA-256 checksums computed
after signing, and investigate detections against those exact hashes. Update
README download links and CITATION.cff only when this release is published;
they currently describe the published 1.7.0 release. Change the 1.7.1 AppStream
entry from development to stable and set its actual release date at publication.

Issue [#5](https://github.com/jabrailkhalil/clickntranslate/issues/5) reports
VirusTotal detections on a portable archive. It does not yet include a public
report URL or the scanned file's hash, so those detections cannot be conclusively
attributed to a particular bundled file. Signing does not prove that software is
malware-free and does not guarantee that every vendor removes a detection.
