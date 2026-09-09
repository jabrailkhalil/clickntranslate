# macOS port (1.7.1 development)

The source implements macOS support for Apple Silicon (`arm64`) and Intel
(`x86_64`). The build targets macOS 13.4 or newer and Python 3.12. Separate native
builds avoid requiring Rosetta or a mixture of incompatible native libraries.

**Status (2026-09-07):** built on an Apple Silicon Mac running macOS 14.3,
installed from DMG, and tested with native Cocoa, LaunchServices, Vision,
the optional OCR engines and translation providers. See [the native QA report](MACOS_QA.md)
for evidence and the remaining manual checks. Intel, macOS 13.4 runtime behavior,
and several permission/input/display scenarios remain unverified. This is a
self-signed development build, without Developer ID or notarization; it is
not yet a notarized public release. Permanent release signing has been checked
on both GitHub runner architectures; this does not establish Intel runtime QA.

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
and EasyOCR are also selectable. The Tesseract Install button now installs a
private native runtime directly into application data, without Homebrew, sudo
or another Python installation. It downloads the pinned, SHA-256-checked official
Micromamba 2.9.0-0 executable and installs Tesseract 5.5.3 from conda-forge for
the current Mac architecture. Micromamba and its package cache are temporary;
no shell initialization is performed. A validated installation manifest is
published atomically; failed/cancelled installation preserves the previous
runtime and its models. Errors do not change the selected OCR engine.

Existing system installations remain supported, including
`brew install tesseract tesseract-lang`. Both the settings window and OCR find
Homebrew when Finder starts the app without the shell's PATH. The package
manager can manage models inside the private Tesseract runtime; it never deletes
system/Homebrew models. Runtime downloads are separate from the signed `.app`.

RapidOCR is bundled in the OCR helper. Optional EasyOCR installs from Settings
without requiring Homebrew or a separate Python installation. If a matching
native Python with pip already exists, the installer reuses it; otherwise it
prepares a private Python of the same minor version and architecture as the
application using the verified Micromamba bootstrap. The temporary Python and
package cache are removed when installation finishes. Errors preserve the
selected OCR engine and any previously installed models. An explicit Mac engine
install also downloads and validates models for the current OCR language and
English; additional languages are installed from Language packages. Recognition
itself never starts an unrequested model download. Intel Macs use the last supported
PyTorch Intel wheel family (2.2.2 / torchvision 0.17.2); Apple Silicon uses native
wheels resolved by pip. The Windows embedded-Python, Tesseract and Hy-MT installers
are never downloaded on macOS.

Hy-MT installs automatically from Settings or Language packages on both Mac
architectures with **macOS 14 or newer**. The official runner requires 14.0;
older systems receive a clear version error before downloading. The rest of the
app retains its 13.4 minimum. The installer downloads the official llama.cpp b9048 native
archive and Tencent's pinned HY-MT1.5-1.8B Q4_K_M GGUF model, checks their SHA-256
hashes, preserves executable permissions and library links, and starts the runner
before reporting success. A failed replacement restores the previous package.
The model, runtime, manifest and licenses stay in application data under
`translators/hymt`; users do not need Homebrew, a compiler or manual file placement.
The progress window supports cancellation and stays attached to its owner.
Translation passes the vendor's plain instruction to llama-cli's chat template,
closes stdin and uses a 4096-token context for bounded input chunks. Echoed prompts
are removed, control-token output is an error, and older malformed cache entries
are ignored. No Hy-MT error switches providers.

Argos is bundled in its helper; Language packages downloads selected directional
pairs automatically. Main-window and hotkey direction arrows remain usable before
the reverse package is installed. Translating with a missing Argos route asks to
install it and continues the same request with progress; cancellation preserves
the draft and the selected provider. Apple Vision and RapidOCR are already ready in the app.
Google, MyMemory, Lingva and LibreTranslate use their configured network services
and do not need local engine packages; a service requiring a key/server must still
be configured by its user. No installation or provider error selects a substitute.

Theme changes freeze the native main window, its separate graphics canvas and
visible dialogs together. Scene, canvas and viewport backgrounds are updated
in one transaction and the viewport is fully repainted, preventing old-theme
strips after scaling. Synthetic Cmd+C/Cmd+V releases the Command event flag before
the next edit command while retaining the foreground-target safety checks.

Copy confirmations use a quiet, non-activating application popup on the current
screen, including shadow mode. They respect the notification checkbox and do not
depend on macOS Notification Center or the presence of a system-tray icon.
The shared OCR language picker shows localized full names and a selected checkmark;
area, fullscreen and dynamic capture use the same themed control on all platforms.

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
The translation pane has a Hide input / Show input control. It gives the result
the full editor area without changing the window size or discarding the source.

The fixed main window now uses Input and Translation tabs in its existing text
panel. Successful manual translations appear inline with scrolling, Copy and
Open in a separate window actions. Switching tabs or rebuilding the main page
preserves the current input and the last result in memory. Each result retains
its original source and language pair when expanded; expanding does not copy it
again. Auto-copy and the explicit clipboard-only result setting still apply.
Provider failures keep the draft and the preceding result available.

Screen capture asks for **Screen Recording** access; copying and replacing a
selection asks for **Accessibility**. The application explains the permission
in its own themed dialog, then opens System Settings on the user's click.
Rejecting a request stops the action; startup never asks for these permissions.
Source launches can appear as Python or Terminal in the permission list.

Local builds now reuse one persistent signing certificate. Ad-hoc signatures
previously tied Screen Recording grants to each executable's changing hash;
System Settings could show an enabled switch while TCC rejected the replacement.
After migrating from an older ad-hoc build, remove the old app entry once and
allow the installed `/Applications/ClicknTranslate.app` again. Subsequent builds
must keep the same certificate. Never reset permissions automatically at startup.

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

For a free local signing identity, provision it once before the first build:

```bash
.venv-macos/bin/python tools/macos_signing.py setup
```

macOS may ask to approve this certificate for the signing tool. The private
identity is stored outside the repository at
`~/Library/Application Support/ClicknTranslateBuild/signing/`. Keep a private
backup of that directory; never upload it, its keychain or password to Git.
It uses one self-signed RSA certificate, a separate encrypted keychain and a
password file readable only by its owner. Trust is scoped to the current user,
the code-signing policy and `/usr/bin/codesign`; SSL, system roots and Gatekeeper
rules are unchanged. The normal build reuses this identity automatically and
fails if it is missing or inconsistent instead of silently switching to ad hoc.
This does not require a paid Apple account and does not provide notarization.

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

Ephemeral PR/manual CI permits explicitly marked ad-hoc QA builds through
`CLICKNTRANSLATE_ALLOW_ADHOC=1`. Tagged release builds restore the permanent
encrypted keychain from two repository Actions secrets:
`MACOS_SIGNING_KEYCHAIN_BASE64` and `MACOS_SIGNING_KEYCHAIN_PASSWORD`.
The same certificate signs both arm64 and Intel releases. Its public certificate
is `packaging/macos/release-certificate.pem`; the pinned SHA-1 fingerprint is
`E5E6A8042F96479E560AED29881A6F06D4D374A2`. Missing secrets or a mismatched signer
fail the release; there is no ad-hoc fallback. PR jobs never restore the key.

To provision or restore these secrets from the original builder, authenticate
the official GitHub CLI as a repository administrator, then run:

```bash
gh auth login --hostname github.com --web --scopes workflow
.venv-macos/bin/python tools/macos_ci_signing.py upload
```

The uploader reads the existing private directory, sends secret values to `gh`
through stdin, and does not print them or write them into the repository. GitHub
CLI encrypts them before upload. The encrypted keychain is transferred intact
because the private key was made nonextractable; no new key is generated.
Keep the original private directory backed up separately. Do not replace its
certificate on another builder: that would change the macOS permission identity.

CI restores the signer under `RUNNER_TEMP/clickntranslate-signing` using
`CLICKNTRANSLATE_SIGNING_DIR`. Only the disposable runner receives administrator
trust for this leaf, scoped to codeSign and `/usr/bin/codesign`. An `always()`
cleanup removes the temporary private files, keychain and public certificate.
The scoped public trust record disappears when GitHub discards the VM;
`remove-trusted-cert` hangs in these headless runners. Self-hosted runners are
refused by the signing helper. Artifacts contain
only public verification reports and release files, never the private keychain.

For a small native check on both runner architectures without an application
build or test suite, dispatch the existing `tests` workflow on the Mac branch:

```bash
gh workflow run tests.yml --ref codex/macos-1.7.1 -f macos_signing_only=true
```

It signs two different tiny executables and verifies they retain the same
certificate requirement, then rejects a valid ad-hoc replacement. The `macOS`
workflow also exposes `signing_only` once available on the default branch.
Tags must point to a commit containing these workflows; configuring a feature
branch does not update an older tag or automatically publish a new release.
See `MACOS_QA.md` for the actual provisioning and runner verification status.

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
