# macOS port (1.7.1 development)

The source implements macOS support for Apple Silicon (`arm64`) and Intel
(`x86_64`). The build targets macOS 13.4 or newer and Python 3.12. Separate native
builds avoid requiring Rosetta or a mixture of incompatible native libraries.

**Status (2026-09-06):** built on an Apple Silicon Mac running macOS 14.3,
installed from DMG, and tested with native Cocoa, LaunchServices, Vision,
the optional OCR engines and translation providers. See [the native QA report](MACOS_QA.md)
for evidence and the remaining manual checks. Intel, macOS 13.4 runtime behavior,
and several permission/input/display scenarios remain unverified. This is an
ad-hoc signed development build, without Developer ID or notarization; it is
not yet a trusted public release. The two-architecture CI has not been dispatched.

For the next agent testing on a real Mac, see [the handoff checklist](MACOS_HANDOFF.md).
It includes source-transfer instructions, exact commands, required manual checks,
and the distinction between completed portable tests and pending native validation.

## Run from source on a Mac

Install Python 3.12, then from the repository root:

```bash
bash tools/setup_macos_env.sh
.venv-macos/bin/python main.py
```

For example, with an existing Homebrew installation, Python is available through
`brew install python@3.12`. The setup script creates `.venv-macos`, installs the
Mac requirements and installs Argos without its unnecessary sentence-splitter
dependency tree. It does not change login items or grant privacy permissions.
Dependency wheels are resolved for the older deployment target even on newer
hosts. The build additionally checks actual Mach-O minimum versions: ONNX
Runtime's current wheel is tagged 13.0 but its binaries require 13.4.

Apple Vision is the default OCR engine and works locally without model downloads.
The language list comes from the installed macOS version. Tesseract, RapidOCR
and EasyOCR are also selectable. Tesseract can be installed using
`brew install tesseract tesseract-lang`; the application also finds Homebrew
when Finder launches it without the shell's PATH. Managed Tesseract models are
stored in application data; the app does not remove system/Homebrew models.

RapidOCR is bundled in the OCR helper. Optional EasyOCR needs a matching Python
3.12 with pip for installation from Settings. Intel Macs use the last supported
PyTorch Intel wheel family (2.2.2 / torchvision 0.17.2); Apple Silicon uses native
wheels resolved by pip. The Windows embedded-Python, Tesseract and Hy-MT installers
are never downloaded on macOS. Hy-MT requires a separately installed compatible
llama.cpp executable and model; its Windows automatic installer remains unavailable.

## Native behavior

| Feature | Implementation |
| --- | --- |
| Text and documents | Existing providers and document formats, shared UI and scaling |
| OCR area, screen, dynamic modes | Selected OCR engine, including Apple Vision and positioned text |
| Retina capture | Native image resolution; logical selection coordinates converted to pixels |
| Shortcuts | Carbon registration of individual combinations, with collision reporting and repeat suppression |
| Selected text | Cmd+C / Cmd+V through Quartz; Accessibility permission requested on use |
| Safe replacement | Foreground process and focused AX window checked; selected text re-read before paste; changed focus falls back to copying the completed translation |
| Dynamic window tracking | Quartz window geometry, foreground window and visibility |
| Shadow mode / menu bar | Keeps the status icon and hotkeys active, hides the main window and Dock icon; Open restores the normal app |
| Dock reopen | Handles the reopen Apple event without replacing Qt's delegate; native deminiaturization preserves the window position |
| Single instance | Existing Unix command channel; Darwin peer PID validation |
| Login startup | Per-user LaunchAgent, enabled only through the existing setting |
| Updates | Opens the release page; does not modify a signed running bundle |

On macOS, **Shadow mode** and the main window's Close button leave the application
in the top menu bar and remove it from the Dock. The status menu provides Open,
Copy Text, Translate, Translate Screen, Dynamic Translation and Quit. Clicking the
status icon opens this menu; Open restores the main window and Dock icon. The
ordinary minimize button still minimizes into the Dock. Automatic login startup
with `start_minimized` uses menu-bar-only shadow mode; manually opening the app
in Finder/Launchpad always shows its window. Qt's native status menu opens after
the button's mouse-down event is consumed, avoiding a second mouse-tracking loop
that can otherwise block reopening after the menu closes. Translation results
can appear while the main window remains hidden. If Ice or another menu-bar manager
hides the icon, move it into that manager's visible section.

Qt stores portable shortcut names as `Ctrl` for Command and `Meta` for physical
Control on macOS. Registration uses that same mapping; the shortcut editor and
main-window references show native Mac labels.

On macOS, 100% interface scale now means a compact 560×320 main window
(80% of the preceding Mac build). Other windows use the same baseline and fit within the screen.
Both panes of the translation window are editable. Translate uses the most
recently edited pane; a draft entered in Translation is first kept in Source,
then translated with the selected language pair and provider. Errors preserve
the draft, and Command-Z can restore the preceding result.

Screen capture asks for **Screen Recording** access; copying and replacing a
selection asks for **Accessibility**. The application explains the permission
in its own themed dialog, then opens System Settings on the user's click.
Rejecting a request stops the action; startup never asks for these permissions.
Source launches can appear as Python or Terminal in the permission list.

Data, settings, caches and downloaded models live in:

```text
~/Library/Application Support/ClicknTranslate/
```

They are shared by the GUI and helpers and survive replacing the application.
No downloaded files are written inside the `.app` bundle. The login item is
`~/Library/LaunchAgents/io.github.jabrailkhalil.clickntranslate.plist`.

## Build a native package

```bash
bash tools/build_macos_release.sh
```

For an explicitly requested build without runtime tests, use
`CLICKNTRANSLATE_SKIP_SMOKE=1 bash tools/build_macos_release.sh`.
Such a build must be recorded as untested; the default still runs the bundle smoke check.

Run on the target architecture. The script builds `dist/ClicknTranslate.app`,
checks its three embedded Python archives and code signatures, exercises the
actual Cocoa GUI through LaunchServices, settings/theme, Vision OCR, Carbon
registration, and both frozen helpers. It verifies the GUI bundle entry point
and every Mach-O deployment target, then creates `.dmg`, `.zip` and SHA-256 files
in `releases/`. For the extended theme/language/scale rendering matrix, run:

```bash
CLICKNTRANSLATE_EXTENDED_SMOKE=1 .venv-macos/bin/python tools/smoke_macos_bundle.py /Applications/ClicknTranslate.app
```

This renders application windows into temporary files before copying the results
to `build/macos`, avoiding a Desktop/Documents permission prompt during smoke QA.
The DMG contains an Applications shortcut: copy the app there before enabling
autostart. The icon uses the original 1024-pixel PNG.

The `macOS` GitHub Actions workflow can be started manually. Pull requests that
change its inputs run it as well. The release workflow calls both Mac builds
before creating a draft release; it uploads only package/checksum assets, not
the smoke-test screenshots. Local native testing does not imply that both CI
architectures have already passed.

For distribution, supply a Developer ID Application identity already present in
the macOS keychain as `MACOS_CODESIGN_IDENTITY`. With a separately provisioned
`MACOS_NOTARY_PROFILE`, the build submits to Apple's notary service, staples the
ticket and checks Gatekeeper acceptance. Without that profile the output is
explicitly identified as a development build. SignPath approval for the Windows
release does not provide Apple's signing identity or notarization.

The signed bundle allows loading optional local inference libraries; it is not
an App Sandbox/Mac App Store package. Store distribution would require a separate
packaging and permission review.

## Required native acceptance checks

After the native workflow passes, check on a real Mac: first-launch permission
denial and approval; a second launch and Dock reopen; shortcuts with Russian and
English layouts; login startup after moving the app to Applications; selection
replacement after changing windows or selections; Retina and mixed-DPI external
displays; capture across Spaces/fullscreen apps; dynamic translation without
capturing its own translated text; both themes and window scaling.

OCR/translation errors do not silently select another engine. Screen and dynamic
screen modes now use the same OCR picker as area capture. A provider failure
keeps completed/cached document parts and reports the failed parts using the
selected provider; it does not send text to a different provider or Argos.
