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

import logging
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
    result = {"uri": "", "response": None}
    loop = QtCore.QEventLoop()

    class PortalResponseReceiver(QtCore.QObject):
        """QtDBus requires a real QObject slot for signal delivery.

        A plain nested Python function looks callable but QDBusConnection
        rejects it at runtime.  Unit tests did not expose that distinction;
        wlroots' real ``Response(uint, a{sv})`` signal does.
        """

        @QtCore.pyqtSlot("uint", "QVariantMap")
        def receive(self, response_code, results):
            result["response"] = int(response_code)
            try:
                result["uri"] = str(results.get("uri", "") or "")
            except AttributeError:
                result["uri"] = ""
            loop.quit()

    receiver = PortalResponseReceiver()

    # The portal is allowed to emit Response before the Screenshot method call
    # itself returns.  Subscribe to the deterministic request path first or a
    # fast compositor (wlroots is one) can finish the screenshot while nobody
    # is listening, leaving the application to wait until the timeout.
    sender = str(bus.baseService() or "").lstrip(":").replace(".", "_")
    request_path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

    connected = bus.connect(
        "org.freedesktop.portal.Desktop",
        request_path,
        "org.freedesktop.portal.Request",
        "Response",
        receiver.receive,
    )
    if not connected:
        raise CaptureError("Could not listen for the portal response.")

    reply = QtDBus.QDBusReply(interface.call("Screenshot", "", options))
    if not reply.isValid():
        bus.disconnect(
            "org.freedesktop.portal.Desktop",
            request_path,
            "org.freedesktop.portal.Request",
            "Response",
            receiver.receive,
        )
        raise CaptureError(f"The portal refused the screenshot request: {reply.error().message()}")

    returned_path = (
        str(reply.value().path()) if hasattr(reply.value(), "path") else str(reply.value())
    )
    if not returned_path:
        bus.disconnect(
            "org.freedesktop.portal.Desktop",
            request_path,
            "org.freedesktop.portal.Request",
            "Response",
            receiver.receive,
        )
        raise CaptureError("The portal returned no request handle.")
    if returned_path != request_path:
        # This should not happen for a valid handle_token, but keep unusual
        # portal implementations usable when their response is not immediate.
        bus.disconnect(
            "org.freedesktop.portal.Desktop",
            request_path,
            "org.freedesktop.portal.Request",
            "Response",
            receiver.receive,
        )
        request_path = returned_path
        if not bus.connect(
            "org.freedesktop.portal.Desktop",
            request_path,
            "org.freedesktop.portal.Request",
            "Response",
            receiver.receive,
        ):
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
            receiver.receive,
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
                env=platform_support.system_subprocess_env(),
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


def looks_blank(pixmap):
    """Whether a grab came back as a single flat black (or empty) image.

    An X11 client on an Xwayland session gets a root window with nothing in it:
    the grab succeeds, reports the full screen size, and every pixel is black,
    because each application is its own Wayland surface. Handing that on as a
    screenshot sends an empty image to OCR, which then reports "no text found" —
    a wrong answer to the wrong question. Only black counts, so a desktop with a
    plain coloured background is not mistaken for a failure.
    """
    if pixmap is None or pixmap.isNull():
        return True
    image = pixmap.toImage()
    if image.isNull() or image.width() < 2 or image.height() < 2:
        return True
    step_x = max(1, image.width() // 24)
    step_y = max(1, image.height() // 24)
    for y in range(0, image.height(), step_y):
        for x in range(0, image.width(), step_x):
            if (image.pixel(x, y) & 0xFFFFFF) != 0x000000:
                return False
    return True


def qt_platform_name():
    """The windowing system Qt actually connected to, not what the environment
    advertises."""
    try:
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        return str(app.platformName()) if app is not None else ""
    except Exception:
        return ""


def grab_screen(screen):
    """Full-screen pixmap for `screen`, using the best available backend.

    Raises CaptureError when nothing on this system can produce a screenshot.
    """
    from PyQt5 import QtGui

    if not platform_support.IS_LINUX:
        return screen.grabWindow(0)

    errors = []
    # Ask Qt what it is running on rather than trusting the environment. A
    # session can export WAYLAND_DISPLAY while this process is an ordinary X11
    # client — every Xwayland app is, and so is anything started on a nested X
    # server from a Wayland login. Reading the environment alone sent those to
    # the portal, which is not there, and capture failed on a display where the
    # plain X11 grab works perfectly.
    blank_x11 = False
    blank_pixmap = None
    platform_name = qt_platform_name()
    logging.info(
        "Screen capture: qt platform=%s, session=%s, portal=%s",
        platform_name or "unknown",
        platform_support.linux_session_type() or "unknown",
        portal_available(),
    )
    if platform_name == "xcb":
        pixmap = screen.grabWindow(0)
        if not looks_blank(pixmap):
            logging.info("Screen capture: used the X11 root grab")
            return pixmap
        # A real Wayland compositor hands an X11 client an empty root. That is
        # not a failure yet: the portal below is exactly for this case.
        blank_x11 = True
        blank_pixmap = pixmap
        errors.append("the X11 screen grab came back empty")

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

    if blank_x11:
        # An all-black grab has two causes and they are not distinguishable from
        # here: an X11 client on a Wayland desktop reading an empty root, or a
        # desktop that is simply black — no wallpaper, and this app hides itself
        # before capturing. The portal above is the fix for the first; if it is
        # not there, hand back what X11 gave us rather than refusing to capture a
        # dark screen. OCR finding no text says the same thing without lying.
        logging.warning(
            "Screen capture: the X11 grab is entirely black. %s", blank_grab_message()
        )
        return blank_pixmap
    raise CaptureError(unavailable_message(errors))


def blank_grab_message():
    """Actionable message for an X11 grab that returned an empty screen."""
    return (
        "Screen capture returned an empty image. This happens when the desktop is "
        f"Wayland and the app is running through Xwayland: only the compositor can read "
        f"the screen. Install {_portal_package()} and log back in, or run an X11 session."
    )


def _portal_package():
    desktop = platform_support.desktop_environment()
    if desktop == "gnome":
        return "xdg-desktop-portal-gnome"
    if desktop == "kde":
        return "xdg-desktop-portal-kde"
    return "xdg-desktop-portal plus the backend for your desktop"


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
