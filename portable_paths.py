import os
import sys


APPMODEL_ERROR_NO_PACKAGE = 15700
ERROR_INSUFFICIENT_BUFFER = 122
PACKAGE_MODE_ENV = "CLICKNTRANSLATE_PACKAGE_MODE"
PACKAGE_FAMILY_ENV = "CLICKNTRANSLATE_PACKAGE_FAMILY"


PUBLIC_EXE_NAME = "ClicknTranslate.exe"
APP_DIR_NAME = "app"
INTERNAL_DIR_NAME = "_internal"


def frozen_executable_dir():
    return os.path.dirname(os.path.abspath(sys.executable))


def windows_package_family_name():
    """Return the current MSIX package family name, or an empty string."""
    override = str(os.environ.get(PACKAGE_FAMILY_ENV, "") or "").strip()
    if override:
        return override
    if sys.platform != "win32":
        return ""
    try:
        import ctypes

        length = ctypes.c_uint32(0)
        get_family_name = ctypes.windll.kernel32.GetCurrentPackageFamilyName
        result = get_family_name(ctypes.byref(length), None)
        if result == APPMODEL_ERROR_NO_PACKAGE:
            return ""
        if result not in (0, ERROR_INSUFFICIENT_BUFFER) or length.value <= 1:
            return ""
        buffer = ctypes.create_unicode_buffer(length.value)
        result = get_family_name(ctypes.byref(length), buffer)
        return buffer.value if result == 0 else ""
    except Exception:
        return ""


def is_windows_packaged():
    """Whether this process is running with MSIX package identity."""
    override = str(os.environ.get(PACKAGE_MODE_ENV, "") or "").strip().lower()
    if override:
        return override in {"1", "true", "yes", "on"}
    return bool(windows_package_family_name())


def packaged_data_dir():
    """Writable per-user state directory used by the Microsoft Store build."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    package_family = windows_package_family_name()
    if package_family:
        return os.path.abspath(
            os.path.join(local_app_data, "Packages", package_family, "LocalState")
        )
    # Deterministic fallback for packaging tests run outside an installed MSIX.
    return os.path.abspath(
        os.path.join(local_app_data, "JabrailDigital", "ClicknTranslate", "StoreData")
    )


def is_launcher_layout():
    if not getattr(sys, "frozen", False):
        return False
    exe_dir = frozen_executable_dir()
    parent_dir = os.path.dirname(exe_dir)
    launcher_path = os.path.join(parent_dir, PUBLIC_EXE_NAME)
    return os.path.basename(exe_dir).lower() == APP_DIR_NAME and os.path.isfile(launcher_path)


def is_internal_worker_layout():
    """Whether a bundled helper is running from the private runtime folder."""
    return (
        bool(getattr(sys, "frozen", False))
        and os.path.basename(frozen_executable_dir()).lower() == INTERNAL_DIR_NAME
    )


def _internal_worker_portable_root():
    runtime_parent = os.path.dirname(frozen_executable_dir())
    if os.path.basename(runtime_parent).lower() == APP_DIR_NAME:
        install_root = os.path.dirname(runtime_parent)
        if os.path.isfile(os.path.join(install_root, PUBLIC_EXE_NAME)):
            return install_root
    return runtime_parent


def portable_base_dir():
    if is_windows_packaged():
        return packaged_data_dir()
    if getattr(sys, "frozen", False):
        if is_internal_worker_layout():
            return _internal_worker_portable_root()
        if is_launcher_layout():
            return os.path.dirname(frozen_executable_dir())
        return frozen_executable_dir()
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def public_executable_path():
    if getattr(sys, "frozen", False):
        if is_internal_worker_layout():
            root = _internal_worker_portable_root()
            public_path = os.path.join(root, PUBLIC_EXE_NAME)
            return os.path.abspath(public_path if os.path.isfile(public_path) else sys.executable)
        if is_launcher_layout():
            return os.path.abspath(os.path.join(portable_base_dir(), PUBLIC_EXE_NAME))
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])
