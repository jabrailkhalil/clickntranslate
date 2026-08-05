# Click'n'Translate on Linux

The Linux build shares all application code with the Windows build. Everything
that differs is isolated in four modules:

| Module | Responsibility |
| --- | --- |
| `platform_support.py` | Which OS this is, XDG directories, executable suffixes, subprocess flags, which OCR engines exist, whether self-update is possible |
| `single_instance.py` | The command socket that replaces global hotkeys |
| `linux_capture.py` | Screen capture through the desktop portal or a compositor helper |
| `linux_desktop.py` | `.desktop` entries, launcher icon, autostart |

Windows behaviour is unchanged: every Windows-only path is still reached through
the same code as before.

## What is different from the Windows build

### Shortcuts are bound in your desktop, not in the app

Linux has no reliable way for an application to grab a global hotkey: X11 grabs
collide with the desktop's own bindings and Wayland forbids them outright. The
same problem is why NormCap documents shortcut setup as an OS task and why
Flameshot asks you to bind `flameshot gui` yourself.

So the app exposes commands instead:

| Command | Action |
| --- | --- |
| `clickntranslate --ocr` | Capture a region and recognize the text |
| `clickntranslate --copy` | Capture a region and copy the text |
| `clickntranslate --translate` | Capture a region and translate it |
| `clickntranslate --fullscreen` | Translate the whole screen |
| `clickntranslate --selection` | Translate the current selection |

Running one of these while the app is already in the tray hands the action to
the running instance over a UNIX socket in `$XDG_RUNTIME_DIR` and exits. If the
app is not running yet, it starts and performs the action once ready.

Bind them like this:

* **GNOME** — Settings → Keyboard → View and Customize Shortcuts → Custom
  Shortcuts → `+`, then enter the command above.
* **KDE Plasma** — System Settings → Shortcuts → Add Command.
* **XFCE** — Settings → Keyboard → Application Shortcuts → Add.

The launcher icon also carries right-click actions for the same commands.

### Screen capture

* **X11** — Qt reads the root window directly, exactly as on Windows.
* **Wayland** — a client may not read the screen, so capture goes through
  `org.freedesktop.portal.Screenshot`. The compositor shows its own permission
  prompt the first time. If the portal is unavailable the app falls back to
  `grim`, `gnome-screenshot` or `spectacle`, and if none of those exist it says
  which portal package to install.

Install the portal backend for your desktop if capture fails:
`xdg-desktop-portal-gnome`, `xdg-desktop-portal-kde` or `xdg-desktop-portal-wlr`.

### OCR engines

Windows OCR does not exist here, so the engine list starts at **Tesseract**,
which is the default. Distributions package it, so the app points you at your
package manager rather than downloading an installer:

```bash
sudo apt install tesseract-ocr tesseract-ocr-rus   # Debian/Ubuntu
sudo dnf install tesseract tesseract-langpack-rus  # Fedora
sudo pacman -S tesseract tesseract-data-rus        # Arch
```

RapidOCR is bundled into the `OcrWorker`, so it works on first launch without
installing anything, exactly as on Windows. EasyOCR stays an optional runtime
install because of its torch payload.

Tesseract data is found wherever your distribution keeps it — Debian's
`/usr/share/tesseract-ocr/<version>/tessdata`, `/usr/share/tessdata` on Fedora
and Arch, or whatever the binary itself reports.

### Updates

The Windows updater replaces its own executable using helper programs written in
C#; none of that ports. On Linux the app reports that a new version exists and
links to the release page. Update by downloading the new AppImage or through
whatever installed the app.

### The tray

Qt only has a tray where the desktop provides one. GNOME needs the AppIndicator
extension; some window managers have none at all. When there is no tray the app
keeps the window reachable instead of hiding into nothing: minimizing goes to
the taskbar, and closing the window exits rather than leaving an invisible
process behind.

### The clipboard

X11 and Wayland keep clipboard contents inside the process that set them, so
text copied by the capture overlay — which exits as soon as it is done — would
disappear unless a clipboard manager happens to be running. The app therefore
hands the text to `wl-copy` (Wayland) or `xclip`/`xsel` (X11), which keep owning
the selection afterwards. Install one if copying seems to do nothing:

```bash
sudo apt install wl-clipboard   # Wayland
sudo apt install xclip          # X11
```

"Translate selection" needs no key simulation here: the highlighted text is
already in the PRIMARY selection, so the app reads it directly and never touches
your clipboard.

### Local translation and OCR engines

* **Hy-MT** — the automatic download is the pinned Windows llama.cpp build, so
  it is not offered here. Put a llama.cpp runner (`llama-cli`, `llama-run`,
  `hymt` or `main`) together with the GGUF model in `translators/hymt` and the
  engine works exactly as on Windows.
* **RapidOCR** — bundled into the `OcrWorker`, so it needs nothing installed.
* **EasyOCR** — installed at runtime with pip and then imported by the frozen
  worker, so it needs a `python3` of the same version this build was made with.
  The app looks for the versioned interpreter first (`python3.12` before
  `python3`) and names the package to install if it is missing.

### Display scaling and the launcher icon

Windows gets per-monitor DPI awareness from its exe manifest, which does not
exist here, so the app enables Qt's high-DPI scaling itself. It also registers
its `.desktop` entry on first run — and again whenever the executable moves,
which is what happens when you download a new AppImage — so the launcher, the
dock and the window switcher show the right icon and the right-click capture
actions.

### Where data lives

A tarball extracted into a writable directory stays portable — config, caches and
downloaded models sit next to the binary, exactly as on Windows. An AppImage is a
read-only mount, so it uses `~/.local/share/clickntranslate` instead.

## Building

```bash
tools/setup_linux_env.sh              # creates ~/.venvs/clickntranslate
tools/build_linux_release.sh          # tarball + AppImage in releases/
```

`ClicknTranslate-linux.spec` builds three executables, mirroring the Windows
layout: the Qt GUI `clickntranslate`, plus `_internal/ArgosWorker` and
`_internal/OcrWorker`. Argos and the neural OCR engines stay out of the Qt
process because their native libraries must not be initialized inside it.

Note that `argostranslate` is installed with `--no-deps`: its dependency tree
pulls in stanza and therefore torch (~2 GB) only for sentence splitting, which
`translater.py` does itself.

## Checking a build

`tools/functional_check.py` drives every feature against the real thing — live
translation providers, the installed Tesseract, the Argos model, the command
socket, the clipboard, the desktop files, and the packaged workers — and prints
a pass/fail matrix:

```bash
python tools/functional_check.py --frozen dist/clickntranslate
python tools/functional_check.py --offline     # skip the live providers
```

It runs on both systems and skips whatever this machine does not have, so a
skip means "not installed here", never "not checked".

## Behaviour shared with Windows that the port improved

Three fixes came out of porting and apply to both systems:

* **Tesseract languages are read from `tesseract --list-langs`** instead of only
  scanning directories next to the binary. Distribution packages keep their
  tessdata elsewhere (`/usr/share/tesseract-ocr/4.00/tessdata` on Debian), and
  the directory scan still covers the portable Windows install.
* **A configured engine that does not exist here falls back to the platform
  default.** A `config.json` copied from Windows names the WinRT engine; the app
  now logs that and uses Tesseract instead of failing on a missing engine.
* **A saved OCR language that is not installed no longer leaves the language
  selector empty** — it falls back to the first installed language rather than
  showing "install a language pack" with no way forward.
* **Tesseract data is located properly.** The app only looked beside the
  binary, which is right for the portable Windows install but finds nothing for
  a distribution package — so the default Linux engine refused to run at all.
  It now also scans the standard system locations and, failing that, trusts a
  binary that reports the language itself.

## Verified so far

Checked in Ubuntu 22.04 (WSL2, headless):

* the packaged `ArgosWorker` translates offline (ru→en) with no torch and no
  onnxruntime present,
* the GUI binary starts, writes its portable `data/config.json`, and creates its
  command socket with `0600` permissions,
* a second launch with `--ocr` or `--translate` delivers the command to the
  running instance and exits,
* Tesseract 4.1.1 is detected from `PATH` and `--list-langs` reports the
  installed languages,
* **the AppImage runs** (157 MB): it starts, keeps its data in
  `~/.local/share/clickntranslate` because the AppImage mount is read-only, and
  accepts a shortcut command from a second launch,
* the test suite passes: 375 passed, 29 skipped on Linux; 393 passed,
  11 skipped on Windows,
* the functional sweep passes: 51 checks on Linux, 34 on Windows, no failures.

Past the first run (the welcome dialog is modal and needs a person to dismiss
it), a headless run also shows:

* the `.desktop` entry and the converted PNG icon appearing in
  `~/.local/share`, with `Exec` pointing at the running executable,
* all three capture overlays constructed on the GUI thread — Qt only allows
  widgets there, and X11 complains where Windows silently tolerated it,
* `clickntranslate --translate` from a second launch logging
  "Shortcut command received: translate" in the running instance, which then
  opens the overlay.

Not yet verified, because it needs a real desktop session: the actual pixels of
a screen grab on X11 and Wayland, the tray icon, and the desktop shortcut
bindings.

On GNOME the tray icon needs the AppIndicator extension — the same requirement
NormCap documents.
