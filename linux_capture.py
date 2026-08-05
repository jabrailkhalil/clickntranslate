"""Screen capture for Linux.

On X11 Qt can grab the root window directly, which is what the Windows build
does too. Wayland forbids that: a client may not read the screen, so the capture
has to go through the desktop portal (or a compositor helper the user already
trusts). This mirrors how Flameshot and NormCap handle Wayland.

Order of preference on Wayland:

1. ``org.freedesktop.portal.Screenshot`` — the sanctioned route, shows the
   compositor's own permission prompt on first use,
2. ``grim`` (wlroots/sway), ``gnome-screenshot``, ``spectacle`` — helpers that
   already have the necessary privileges,
3. nothing: the caller gets a message explaining what to install.
"""

import os
import shutil
import subprocess
import tempfile
import uuid

import platform_support


class CaptureError(RuntimeError):
    """Raised when no capture backend can produce an image."""


#: External helpers, in the order they are tried. Each entry builds the command
#: that writes a PNG to the given path.
HELPERS = (
    ("grim", lambda path: ["grim", path]),
    ("gnome-screenshot", lambda path: ["gnome-screenshot", "-f", path]),
    ("spectacle", lambda path: ["spectacle", "-b", "-n", "-o", path]),
    ("import", lambda path: ["import", "-window", "root", path]),
)

_HELPER_TIMEOUT = 15
_PORTAL_TIMEOUT_MS = 20000


def _temp_png_path():
    directory = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return os.path.join(directory, f"clickntranslate-capture-{uuid.uuid4().hex}.png")


def available_helper():
    """First screenshot helper installed on this system, or ""."""
    for name, _command in HELPERS:
        if shutil.which(name):
            return name
    return ""


def backend_name():
    """Which backend a capture would use right now."""
    if not platform_support.IS_LINUX:
        return "qt"
    if not platform_support.is_wayland():
        return "qt"
    if portal_available():
        return "portal"
    helper = available_helper()
    return helper or ""


def portal_available():
    """Whether the desktop portal exposes the Screenshot interface."""
    if not platform_support.IS_LINUX:
        return False
    try:
        from PyQt5 import QtDBus
    except Exception:
        return False
    try:
        bus = QtDBus.QDBusConnection.sessionBus()
        if not bus.isConnected():
            return False
        interface = QtDBus.QDBusInterface(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            bus,
        )
        return bool(interface.isValid())
    except Exception:
        return False


def capture_with_portal():
    """Ask the desktop portal for a screenshot. Returns a PNG path.

    The portal answers asynchronously: the method call returns the object path
    of a request, and the image URI arrives on that request's Response signal.
    """
    from PyQt5 import QtCore, QtDBus

    bus = QtDBus.QDBusConnection.sessionBus()
    if not bus.isConnected():
        raise CaptureError("The session D-Bus is not reachable.")

    interface = QtDBus.QDBusInterface(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.Screenshot",
        bus,
    )
    if not interface.isValid():
        raise CaptureError("The desktop portal does not provide a Screenshot interface.")

    token = f"clickntranslate_{uuid.uuid4().hex}"
    options = {
        "handle_token": token,
        # Non-interactive: we want the whole screen, the app does its own
        # region selection afterwards.
        "interactive": False,
    }
    reply = QtDBus.QDBusReply(interface.call("Screenshot", "", options))
    if not reply.isValid():
        raise CaptureError(f"The portal refused the screenshot request: {reply.error().message()}")

    request_path = str(reply.value().path()) if hasattr(reply.value(), "path") else str(reply.value())
    if not request_path:
        raise CaptureError("The portal returned no request handle.")

    result = {"uri": "", "response": None}
    loop = QtCore.QEventLoop()

    def on_response(response_code, results):
        result["response"] = int(response_code)
        try:
            result["uri"] = str(results.get("uri", "") or "")
        except AttributeError:
            result["uri"] = ""
        loop.quit()

    connected = bus.connect(
        "org.freedesktop.portal.Desktop",
        request_path,
        "org.freedesktop.portal.Request",
        "Response",
        on_response,
    )
    if not connected:
        raise CaptureError("Could not listen for the portal response.")

    timer = QtCore.QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(_PORTAL_TIMEOUT_MS)
    try:
        loop.exec_()
    finally:
        timer.stop()
        bus.disconnect(
            "org.freedesktop.portal.Desktop",
            request_path,
            "org.freedesktop.portal.Request",
            "Response",
            on_response,
        )

    if result["response"] is None:
        raise CaptureError("The desktop portal did not answer the screenshot request.")
    if result["response"] != 0:
        # 1 = cancelled by the user, 2 = ended some other way.
        raise CaptureError("The screenshot permission was declined.")

    path = uri_to_path(result["uri"])
    if not path or not os.path.isfile(path):
        raise CaptureError("The portal reported success but produced no image.")
    return path


def uri_to_path(uri):
    """Local filesystem path for a file:// URI."""
    from urllib.parse import unquote, urlparse

    text = str(uri or "")
    if not text:
        return ""
    if not text.startswith("file://"):
        return text
    parsed = urlparse(text)
    return unquote(parsed.path)


def capture_with_helper(helper=None):
    """Run an external screenshot helper. Returns a PNG path."""
    commands = dict(HELPERS)
    names = [helper] if helper else [name for name, _ in HELPERS]
    errors = []
    for name in names:
        if name not in commands or not shutil.which(name):
            continue
        path = _temp_png_path()
        try:
            completed = subprocess.run(
                commands[name](path),
                capture_output=True,
                text=True,
                timeout=_HELPER_TIMEOUT,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"{name}: {exc}")
            continue
        if completed.returncode == 0 and os.path.isfile(path) and os.path.getsize(path) > 0:
            return path
        errors.append(f"{name}: exit {completed.returncode} {(completed.stderr or '').strip()[:120]}")
        _discard(path)
    raise CaptureError("; ".join(errors) if errors else "No screenshot helper is installed.")


def _discard(path):
    try:
        if path and os.path.isfile(path):
            os.unlink(path)
    except OSError:
        pass


def crop_to_screen(pixmap, screen):
    """Cut one screen out of a whole-desktop grab.

    Portals and helpers hand back every monitor in one image, while the caller
    works per screen, so a multi-monitor result has to be cropped to the screen
    it asked for.
    """
    if pixmap.isNull() or screen is None:
        return pixmap
    try:
        geometry = screen.geometry()
        ratio = pixmap.width() / max(1, _desktop_width(screen))
    except Exception:
        return pixmap
    if ratio <= 0:
        return pixmap
    expected_width = int(round(geometry.width() * ratio))
    expected_height = int(round(geometry.height() * ratio))
    if pixmap.width() <= expected_width and pixmap.height() <= expected_height:
        return pixmap
    return pixmap.copy(
        int(round(geometry.x() * ratio)),
        int(round(geometry.y() * ratio)),
        expected_width,
        expected_height,
    )


def _desktop_width(screen):
    """Width of the whole virtual desktop in logical pixels."""
    try:
        from PyQt5.QtWidgets import QApplication

        screens = QApplication.screens() or [screen]
    except Exception:
        screens = [screen]
    right_edges = [scr.geometry().x() + scr.geometry().width() for scr in screens]
    return max(right_edges) if right_edges else screen.geometry().width()


def grab_screen(screen):
    """Full-screen pixmap for `screen`, using the best available backend.

    Raises CaptureError when Wayland blocks the capture and no portal or helper
    can stand in.
    """
    from PyQt5 import QtGui

    if not platform_support.IS_LINUX or not platform_support.is_wayland():
        return screen.grabWindow(0)

    errors = []
    if portal_available():
        try:
            path = capture_with_portal()
            try:
                pixmap = QtGui.QPixmap(path)
                if not pixmap.isNull():
                    return crop_to_screen(pixmap, screen)
                errors.append("portal: the returned image could not be read")
            finally:
                _discard(path)
        except CaptureError as exc:
            errors.append(str(exc))

    try:
        path = capture_with_helper()
        try:
            pixmap = QtGui.QPixmap(path)
            if not pixmap.isNull():
                return crop_to_screen(pixmap, screen)
            errors.append("helper: the returned image could not be read")
        finally:
            _discard(path)
    except CaptureError as exc:
        errors.append(str(exc))

    raise CaptureError(unavailable_message(errors))


def unavailable_message(errors=()):
    """Actionable message for a Wayland session that cannot be captured."""
    desktop = platform_support.desktop_environment()
    if desktop == "gnome":
        package = "xdg-desktop-portal-gnome"
    elif desktop == "kde":
        package = "xdg-desktop-portal-kde"
    else:
        package = "xdg-desktop-portal plus the backend for your desktop"
    detail = f" ({'; '.join(errors)})" if errors else ""
    return (
        "Screen capture is not permitted in this Wayland session. "
        f"Install {package} and log back in, or start an X11 session instead." + detail
    )
