"""Freedesktop integration: desktop entries, icons and autostart.

Windows uses a Startup-folder shortcut (or an MSIX StartupTask); Linux uses a
`.desktop` file in `~/.config/autostart`. The same file format also puts the app
in the application menu, and its desktop actions give the tray-less desktops a
right-click menu for the capture commands.
"""

import os
import shutil

import platform_support


APP_NAME = "Click'n'Translate"
ICON_NAME = "clickntranslate"
COMMENT = "Recognize text on screen and translate it"
LEGACY_DESKTOP_ENTRY_NAME = "clickntranslate.desktop"

#: Right-click actions on the launcher icon, mirroring the Windows hotkeys.
DESKTOP_ACTIONS = (
    ("Toggle", "Show or hide Click'n'Translate", "toggle"),
    ("Capture", "Capture text", "ocr"),
    ("Copy", "Copy text from screen", "copy"),
    ("Translate", "Translate text on screen", "translate"),
    ("Fullscreen", "Translate the whole screen", "fullscreen"),
)


def autostart_path():
    return os.path.join(platform_support.autostart_dir(), platform_support.DESKTOP_ENTRY_NAME)


def application_entry_path():
    return os.path.join(platform_support.applications_dir(), platform_support.DESKTOP_ENTRY_NAME)


def _legacy_entry_path(directory):
    return os.path.join(directory, LEGACY_DESKTOP_ENTRY_NAME)


def _remove_file(path):
    try:
        if os.path.isfile(path) or os.path.islink(path):
            os.unlink(path)
    except OSError:
        return False
    return not os.path.exists(path)


def _escape(value):
    """Escape a value for a desktop entry key."""
    return str(value or "").replace("\\", "\\\\").replace("\n", " ")


def _exec_value(executable, argument=""):
    """Exec= value, quoted when the path contains spaces."""
    command = _escape(executable)
    if " " in command:
        command = f'"{command}"'
    return f"{command} {argument}".strip()


def desktop_entry_text(executable, autostart=False, include_actions=True):
    """Contents of a .desktop file pointing at `executable`."""
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={APP_NAME}",
        "GenericName=Screen translator",
        f"Comment={COMMENT}",
        f"Exec={_exec_value(executable)}",
        f"Icon={ICON_NAME}",
        "Terminal=false",
        # Keep one freedesktop main category.  Multiple main categories make
        # some menus show the application twice, and Translation is specified
        # as a development subcategory rather than a general-language tool.
        "Categories=Utility;Qt;",
        "Keywords=translation;translator;OCR;screen;capture;text;",
        "StartupNotify=false",
        "StartupWMClass=ClicknTranslate",
    ]
    if autostart:
        # Honoured by GNOME; other desktops simply ignore it.
        lines.append("X-GNOME-Autostart-enabled=true")
    if include_actions:
        lines.append("Actions=" + ";".join(name for name, _label, _action in DESKTOP_ACTIONS) + ";")
        for name, label, action in DESKTOP_ACTIONS:
            lines.extend(
                [
                    "",
                    f"[Desktop Action {name}]",
                    f"Name={label}",
                    f"Exec={_exec_value(executable, '--' + action)}",
                ]
            )
    return "\n".join(lines) + "\n"


def _write_entry(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(path, 0o755)
    return path


def set_autostart(enabled, executable):
    """Create or remove the autostart entry. Returns the resulting state."""
    path = autostart_path()
    if not enabled:
        _remove_file(path)
        _remove_file(_legacy_entry_path(platform_support.autostart_dir()))
        return autostart_enabled()
    try:
        _write_entry(path, desktop_entry_text(executable, autostart=True, include_actions=False))
        _remove_file(_legacy_entry_path(platform_support.autostart_dir()))
    except OSError:
        return False
    return True


def autostart_enabled():
    return os.path.isfile(autostart_path()) or os.path.isfile(
        _legacy_entry_path(platform_support.autostart_dir())
    )


def install_desktop_entry(executable, icon_source=""):
    """Add the app to the application menu. Returns the entry path."""
    path = _write_entry(application_entry_path(), desktop_entry_text(executable))
    _remove_file(_legacy_entry_path(platform_support.applications_dir()))
    if icon_source and os.path.isfile(icon_source):
        install_icon(icon_source)
    return path


def install_icon(icon_source, size="256x256"):
    """Put an icon into the hicolor theme so the launcher can show it.

    The repository ships a Windows .ico; icon themes need a PNG, so one is
    converted on the way in.
    """
    target_dir = platform_support.icons_dir(size)
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, f"{ICON_NAME}.png")

    if os.path.splitext(icon_source)[1].lower() == ".png":
        shutil.copyfile(icon_source, target)
        return target

    from PIL import Image

    with Image.open(icon_source) as image:
        # An .ico holds several sizes; take the largest one.
        if getattr(image, "n_frames", 1) > 1:
            best, best_area = image, 0
            for index in range(image.n_frames):
                image.seek(index)
                area = image.width * image.height
                if area > best_area:
                    best, best_area = image.copy(), area
            image = best
        pixels = int(size.split("x")[0])
        image.convert("RGBA").resize((pixels, pixels), Image.LANCZOS).save(target, "PNG")
    return target


def remove_desktop_entry():
    for path in (
        application_entry_path(),
        autostart_path(),
        _legacy_entry_path(platform_support.applications_dir()),
        _legacy_entry_path(platform_support.autostart_dir()),
    ):
        _remove_file(path)
