"""Operating system specifics for Click'n'Translate.

Everything that behaves differently on Windows and Linux lives here, so the rest
of the app can stay platform-neutral. The Windows implementations reproduce what
1.5.5 already shipped; the Linux ones follow the conventions used by comparable
Linux tools (NormCap, Flameshot):

* no in-app global hotkeys — the user binds a command in the desktop
  environment's own keyboard settings (see `shortcut_command`),
* screen capture through the desktop portal on Wayland and Qt on X11,
* XDG base directories and a freedesktop autostart entry.
"""

import os
import shutil
import subprocess
import sys


IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")
IS_MAC = sys.platform == "darwin"

#: Reverse-DNS identifier used for desktop entries, icons and the IPC socket.
APP_ID = "io.github.jabrailkhalil.ClicknTranslate"
DESKTOP_ENTRY_NAME = "clickntranslate.desktop"
LINUX_BINARY_NAME = "clickntranslate"

#: Suffix for bundled helper executables (ArgosWorker, OcrWorker, ...).
EXECUTABLE_SUFFIX = ".exe" if IS_WINDOWS else ""


def executable_name(stem):
    """Platform file name for a bundled helper executable."""
    return f"{stem}{EXECUTABLE_SUFFIX}"


# --- session / display server -------------------------------------------------


def linux_session_type():
    """"wayland", "x11" or "" when the session type cannot be determined."""
    if not IS_LINUX:
        return ""
    session = str(os.environ.get("XDG_SESSION_TYPE", "") or "").strip().lower()
    if session in {"wayland", "x11"}:
        return session
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return ""


def is_wayland():
    return linux_session_type() == "wayland"


def has_display():
    """Whether a graphical session is reachable at all."""
    if not IS_LINUX:
        return True
    return bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))


def desktop_environment():
    """Lower-case desktop name, e.g. "gnome", "kde", or "" when unknown."""
    if not IS_LINUX:
        return ""
    for variable in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        value = str(os.environ.get(variable, "") or "").strip().lower()
        if value:
            # XDG_CURRENT_DESKTOP may be a colon separated list such as "ubuntu:GNOME".
            for part in value.split(":"):
                if part in {"gnome", "kde", "plasma", "xfce", "cinnamon", "mate", "lxqt", "sway", "hyprland"}:
                    return "kde" if part == "plasma" else part
            return value.split(":")[0]
    return ""


# --- subprocess ---------------------------------------------------------------


def no_window_kwargs():
    """Keyword arguments that keep a child process from flashing a console.

    Windows needs STARTUPINFO/CREATE_NO_WINDOW; nothing is required elsewhere.
    """
    if not IS_WINDOWS:
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "startupinfo": startupinfo,
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
    }


# --- XDG base directories -----------------------------------------------------


def _xdg_dir(variable, fallback_parts):
    value = str(os.environ.get(variable, "") or "").strip()
    if value and os.path.isabs(value):
        return value
    return os.path.join(os.path.expanduser("~"), *fallback_parts)


def xdg_config_home():
    return _xdg_dir("XDG_CONFIG_HOME", (".config",))


def xdg_data_home():
    return _xdg_dir("XDG_DATA_HOME", (".local", "share"))


def xdg_cache_home():
    return _xdg_dir("XDG_CACHE_HOME", (".cache",))


def autostart_dir():
    return os.path.join(xdg_config_home(), "autostart")


def applications_dir():
    return os.path.join(xdg_data_home(), "applications")


def icons_dir(size="256x256"):
    return os.path.join(xdg_data_home(), "icons", "hicolor", size, "apps")


# --- AppImage -----------------------------------------------------------------


def appimage_path():
    """Path of the running AppImage, or "" when not running from one."""
    return str(os.environ.get("APPIMAGE", "") or "") if IS_LINUX else ""


def is_appimage():
    return bool(appimage_path())


# --- shortcuts ----------------------------------------------------------------

#: Command line actions a desktop shortcut can invoke. These mirror the Windows
#: hotkey actions, which Linux users bind themselves in their desktop settings.
SHORTCUT_ACTIONS = ("ocr", "copy", "translate", "fullscreen", "selection")


def shortcut_command(action, executable=None):
    """Command a user binds to a key in their desktop environment."""
    if action not in SHORTCUT_ACTIONS:
        raise ValueError(f"Unknown shortcut action: {action}")
    if executable is None:
        executable = appimage_path() or LINUX_BINARY_NAME
    if " " in executable:
        executable = f'"{executable}"'
    return f"{executable} --{action}"


# --- clipboard ----------------------------------------------------------------


def missing_clipboard_helper():
    """Name of the clipboard helper a Linux desktop is missing, or "".

    Qt handles the clipboard while the app is running, but text copied by a
    process that then exits needs a clipboard manager or one of these helpers.
    """
    if not IS_LINUX:
        return ""
    if is_wayland():
        return "" if shutil.which("wl-copy") else "wl-clipboard"
    return "" if (shutil.which("xclip") or shutil.which("xsel")) else "xclip"


# --- OCR engines --------------------------------------------------------------

#: Engines offered on each platform. "windows" is the WinRT engine and only
#: exists on Windows; Tesseract is the Linux default because distributions
#: package it, so it needs no bundled installer.
WINDOWS_OCR_ENGINES = ("windows", "tesseract", "rapidocr", "easyocr")
LINUX_OCR_ENGINES = ("tesseract", "rapidocr", "easyocr")


def available_ocr_engines():
    return WINDOWS_OCR_ENGINES if IS_WINDOWS else LINUX_OCR_ENGINES


def default_ocr_engine():
    return "Windows" if IS_WINDOWS else "Tesseract"


def supports_windows_ocr():
    return IS_WINDOWS


def system_tesseract_command():
    """Tesseract found on PATH, or "" when it is not installed."""
    return shutil.which("tesseract") or ""


#: How a user installs Tesseract, per package manager. Linux distributions ship
#: it, so the app points at the package instead of downloading an installer.
TESSERACT_INSTALL_HINTS = (
    ("apt-get", "sudo apt install tesseract-ocr tesseract-ocr-<lang>"),
    ("dnf", "sudo dnf install tesseract tesseract-langpack-<lang>"),
    ("pacman", "sudo pacman -S tesseract tesseract-data-<lang>"),
    ("zypper", "sudo zypper install tesseract-ocr tesseract-ocr-traineddata-<lang>"),
)


def tesseract_install_hint():
    """Install command for the detected package manager."""
    for manager, hint in TESSERACT_INSTALL_HINTS:
        if shutil.which(manager):
            return hint
    return TESSERACT_INSTALL_HINTS[0][1]


# --- updates ------------------------------------------------------------------


def supports_in_app_update():
    """Whether the app may replace itself.

    Only the Windows build ships the updater helpers. Linux packages are updated
    by whatever installed them, so the app only reports that a version exists.
    """
    return IS_WINDOWS
