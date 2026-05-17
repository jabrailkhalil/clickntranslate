import os
import sys


PUBLIC_EXE_NAME = "ClicknTranslate.exe"
APP_DIR_NAME = "app"


def frozen_executable_dir():
    return os.path.dirname(os.path.abspath(sys.executable))


def is_launcher_layout():
    if not getattr(sys, "frozen", False):
        return False
    exe_dir = frozen_executable_dir()
    parent_dir = os.path.dirname(exe_dir)
    launcher_path = os.path.join(parent_dir, PUBLIC_EXE_NAME)
    return os.path.basename(exe_dir).lower() == APP_DIR_NAME and os.path.isfile(launcher_path)


def portable_base_dir():
    if getattr(sys, "frozen", False):
        if is_launcher_layout():
            return os.path.dirname(frozen_executable_dir())
        return frozen_executable_dir()
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def public_executable_path():
    if getattr(sys, "frozen", False):
        if is_launcher_layout():
            return os.path.abspath(os.path.join(portable_base_dir(), PUBLIC_EXE_NAME))
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])
