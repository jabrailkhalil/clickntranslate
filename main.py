import json
import getpass
import os
import sys
import warnings  # suppress noisy third-party warnings
# гасим предупреждение pkg_resources ДО первых сторонних импортов
warnings.filterwarnings(
    "ignore",
    message=r"pkg_resources is deprecated as an API",
    category=UserWarning,
)
warnings.filterwarnings("ignore", category=UserWarning, module=r"pkg_resources")
import subprocess
import ctypes
import threading
import time


def _show_dependency_error():
    message = (
        "Click'n'Translate не запускается: не найдена библиотека PyQt5.\n\n"
        "Запустите в консоли:\n"
        "  python -m pip install -r requirements.txt\n\n"
        "Или только Qt:\n"
        "  python -m pip install PyQt5"
    )
    print(message)
    raise SystemExit(1)

try:
    import pyperclip
except Exception:
    class _PyperclipFallback:
        @staticmethod
        def _clipboard():
            try:
                app = QApplication.instance()
                if app is None:
                    return None
                return app.clipboard()
            except Exception:
                return None

        @staticmethod
        def copy(text):
            clipboard = _PyperclipFallback._clipboard()
            if clipboard is None:
                return
            try:
                clipboard.setText(str(text))
            except Exception:
                pass

        @staticmethod
        def paste():
            clipboard = _PyperclipFallback._clipboard()
            if clipboard is None:
                return ""
            try:
                return clipboard.text()
            except Exception:
                return ""

    pyperclip = _PyperclipFallback
from ctypes import wintypes
import psutil
import datetime
import urllib.parse
import webbrowser

try:
    from PyQt5 import QtCore
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QVBoxLayout, QComboBox,
                                 QWidget, QPushButton, QSystemTrayIcon, QMenu, QMessageBox, QLineEdit, QTextEdit, QDialog, QHBoxLayout, QCheckBox, QSpacerItem, QSizePolicy, QProgressDialog, QFrame, QGraphicsDropShadowEffect, QFileDialog, QProgressBar, QSplitter)
    from PyQt5.QtCore import Qt, QTimer, QSize
    from PyQt5.QtGui import QIcon, QColor, QPixmap, QPainter, QPen, QBrush, QPolygonF
except Exception:
    _show_dependency_error()
from settings_window import SettingsWindow
from app_version import APP_VERSION
import portable_paths
import translater  # Импорт модуля перевода
from document_parser import DocumentParseError, format_file_size, parse_document
from document_parser import SUPPORTED_EXTENSIONS
from document_storage import default_output_paths, load_session, save_session, save_text, translations_dir
from document_translation import translate_document_text
from languages import (
    default_target_for_source,
    detect_language_code,
    language_code_from_name,
    language_names,
)

AUTOSTART_SHORTCUT_NAME = "ClicknTranslate.lnk"
AUTOSTART_BACKEND = "startup_shortcut"

INTERFACE_LANGUAGE_OPTIONS = [
    {"code": "en", "name": "English", "icon": "icons/American_flag.png"},
    {"code": "ru", "name": "Русский", "icon": "icons/Russian_flag.png"},
    {"code": "es", "name": "Español", "icon": "icons/Spanish_flag.png"},
    {"code": "de", "name": "Deutsch", "icon": "icons/German_flag.png"},
    {"code": "fr", "name": "Français", "icon": "icons/French_flag.png"},
    {"code": "zh", "name": "中文", "icon": "icons/Chinese_flag.png"},
]
INTERFACE_LANGUAGE_BY_CODE = {item["code"]: item for item in INTERFACE_LANGUAGE_OPTIONS}

# --- Единственная константа с дефолтной конфигурацией ---
DEFAULT_CONFIG = {
    "theme": "Темная",
    "interface_language": "en",
    "autostart": False,
    "autostart_backend": AUTOSTART_BACKEND,
    "translation_mode": "English",
    "copy_hotkey": "Ctrl+Alt+C",
    "translate_hotkey": "Ctrl+Alt+T",
    "notifications": False,
    "history": False,
    "start_minimized": False,
    "show_update_info": True,  # Показывать Welcome окно при первом запуске
    "first_run_guide_completed": False,
    "first_run_guide_pending": False,
    "ocr_engine": "Windows",
    "translator_engine": "Google",
    "allow_online_provider_fallback": False,
    "copy_history": False,
    "copy_translated_text": False,  # Все галочки отключены по умолчанию
    "keep_visible_on_ocr": False,
    "freeze_screen_on_ocr": False,
    "debug_ocr_artifacts": False,
    "last_ocr_language": "ru",
    "ocr_translate_source_language": "en",
    "ocr_translate_target_language": "ru",
    "no_screen_dimming": False,
    "fullscreen_translate_hotkey": "Ctrl+Alt+F",
    "translate_selection_hotkey": "Ctrl+Alt+Q"
}


def normalize_interface_language(language_code):
    code = str(language_code or "").lower()
    if code in INTERFACE_LANGUAGE_BY_CODE:
        return code
    return DEFAULT_CONFIG["interface_language"]


def get_interface_language_option(language_code):
    return INTERFACE_LANGUAGE_BY_CODE.get(
        normalize_interface_language(language_code),
        INTERFACE_LANGUAGE_BY_CODE[DEFAULT_CONFIG["interface_language"]],
    )


def apply_windows_dark_frame(widget, enabled=True):
    if sys.platform != "win32" or widget is None:
        return
    try:
        hwnd = int(widget.winId())
        dwmapi = ctypes.windll.dwmapi
        dark_value = ctypes.c_int(1 if enabled else 0)
        for attribute in (20, 19):
            try:
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    ctypes.c_uint(attribute),
                    ctypes.byref(dark_value),
                    ctypes.sizeof(dark_value),
                )
            except Exception:
                pass

        if enabled:
            border_color = ctypes.c_uint(0x000000)
            caption_color = ctypes.c_uint(0x000000)
            text_color = ctypes.c_uint(0xFFFFFF)
        else:
            default_color = ctypes.c_uint(0xFFFFFFFF)
            border_color = caption_color = text_color = default_color

        for attribute, value in ((34, border_color), (35, caption_color), (36, text_color)):
            try:
                dwmapi.DwmSetWindowAttribute(
                    wintypes.HWND(hwnd),
                    ctypes.c_uint(attribute),
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
            except Exception:
                pass
    except Exception:
        pass


def _frozen_executable_dir():
    return portable_paths.frozen_executable_dir()


def _portable_base_dir():
    return portable_paths.portable_base_dir()


def _public_executable_path():
    return portable_paths.public_executable_path()


def _autostart_startup_dir():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(
            appdata,
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
            "Startup",
        )
    return os.path.join(
        os.path.expanduser("~"),
        "AppData",
        "Roaming",
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
    )


def _autostart_shortcut_path():
    return os.path.join(_autostart_startup_dir(), AUTOSTART_SHORTCUT_NAME)


def _current_autostart_shortcut_info():
    """Return target/arguments for the Startup folder shortcut."""
    if getattr(sys, "frozen", False):
        target = _public_executable_path()
        return {
            "target": target,
            "arguments": "--autostart",
            "working_dir": os.path.dirname(target),
            "icon": f"{target},0",
        }

    python_exe = os.path.abspath(sys.executable)
    pythonw = python_exe
    if os.path.basename(python_exe).lower() == "python.exe":
        candidate = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        pythonw = candidate if os.path.exists(candidate) else python_exe

    script_path = os.path.abspath(sys.argv[0])
    return {
        "target": pythonw,
        "arguments": subprocess.list2cmdline([script_path, "--autostart"]),
        "working_dir": os.path.dirname(script_path),
        "icon": os.path.abspath(os.path.join(get_app_dir(), "icons", "icon.ico")),
    }


def _build_autostart_command():
    info = _current_autostart_shortcut_info()
    parts = [info["target"]]
    if info["arguments"]:
        parts.extend(_parse_windows_command_line(info["arguments"]))
    return subprocess.list2cmdline(parts)


def _parse_windows_command_line(command):
    command = str(command or "").strip()
    if not command:
        return []
    try:
        argc = ctypes.c_int(0)
        command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
        command_line_to_argv.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
        command_line_to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
        argv = command_line_to_argv(command, ctypes.byref(argc))
        if not argv:
            return []
        try:
            return [argv[i] for i in range(argc.value)]
        finally:
            local_free = ctypes.windll.kernel32.LocalFree
            local_free.argtypes = [wintypes.HLOCAL]
            local_free.restype = wintypes.HLOCAL
            local_free(argv)
    except Exception:
        return [command.strip('"')]


def _normalize_autostart_arg(arg):
    value = os.path.expandvars(str(arg or "").strip().strip('"'))
    if not value:
        return ""
    value = value.replace("/", "\\")
    if os.path.isabs(value):
        return os.path.normcase(os.path.abspath(value))
    return value.lower()


def _normalize_autostart_command(command):
    return tuple(
        _normalize_autostart_arg(arg)
        for arg in _parse_windows_command_line(command)
        if str(arg or "").strip()
    )


def _autostart_commands_equivalent(left, right):
    left_norm = _normalize_autostart_command(left)
    right_norm = _normalize_autostart_command(right)
    return bool(left_norm and right_norm and left_norm == right_norm)


def _ps_single_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _run_hidden_powershell(script):
    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        startupinfo=startupinfo,
        creationflags=creationflags,
        timeout=15,
    )


def _write_autostart_shortcut():
    info = _current_autostart_shortcut_info()
    shortcut_path = _autostart_shortcut_path()
    os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$ws = New-Object -ComObject WScript.Shell",
            f"$shortcut = $ws.CreateShortcut({_ps_single_quote(shortcut_path)})",
            f"$shortcut.TargetPath = {_ps_single_quote(info['target'])}",
            f"$shortcut.Arguments = {_ps_single_quote(info['arguments'])}",
            f"$shortcut.WorkingDirectory = {_ps_single_quote(info['working_dir'])}",
            f"$shortcut.IconLocation = {_ps_single_quote(info['icon'])}",
            "$shortcut.WindowStyle = 7",
            "$shortcut.Save()",
        ]
    )
    result = _run_hidden_powershell(script)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "Failed to create Startup shortcut").strip())


def _read_autostart_shortcut():
    shortcut_path = _autostart_shortcut_path()
    if not os.path.exists(shortcut_path):
        return None
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)",
            "$ws = New-Object -ComObject WScript.Shell",
            f"$shortcut = $ws.CreateShortcut({_ps_single_quote(shortcut_path)})",
            "@{",
            "  TargetPath = $shortcut.TargetPath",
            "  Arguments = $shortcut.Arguments",
            "  WorkingDirectory = $shortcut.WorkingDirectory",
            "} | ConvertTo-Json -Compress",
        ]
    )
    result = _run_hidden_powershell(script)
    if result.returncode != 0:
        return {"target": "", "arguments": "", "working_dir": ""}
    try:
        data = json.loads(result.stdout or "{}")
    except Exception:
        data = {}
    return {
        "target": str(data.get("TargetPath") or ""),
        "arguments": str(data.get("Arguments") or ""),
        "working_dir": str(data.get("WorkingDirectory") or ""),
    }


def _autostart_shortcut_matches_current(shortcut_info):
    if not shortcut_info:
        return False
    expected = _current_autostart_shortcut_info()
    left = [shortcut_info.get("target", "")]
    left.extend(_parse_windows_command_line(shortcut_info.get("arguments", "")))
    right = [expected["target"]]
    right.extend(_parse_windows_command_line(expected.get("arguments", "")))
    return _autostart_commands_equivalent(
        subprocess.list2cmdline(left),
        subprocess.list2cmdline(right),
    )


def _write_autostart_command(enable):
    shortcut_path = _autostart_shortcut_path()
    if enable:
        _write_autostart_shortcut()
        return

    try:
        os.remove(shortcut_path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _read_autostart_command():
    shortcut_info = _read_autostart_shortcut()
    if not shortcut_info:
        return ""
    parts = [shortcut_info.get("target", "")]
    parts.extend(_parse_windows_command_line(shortcut_info.get("arguments", "")))
    return subprocess.list2cmdline([part for part in parts if str(part or "").strip()])

# --- Глобальный кэш конфигурации ---
_config_cache = None
_config_mtime = 0

def get_cached_config():
    """Возвращает закэшированную конфигурацию, перечитывая только при изменении файла."""
    global _config_cache, _config_mtime
    config_path = get_data_file("config.json")
    try:
        mtime = os.path.getmtime(config_path)
        if _config_cache is None or mtime > _config_mtime:
            with open(config_path, "r", encoding="utf-8-sig") as f:
                _config_cache = json.load(f)
            _config_mtime = mtime
    except Exception:
        if _config_cache is None:
            _config_cache = DEFAULT_CONFIG.copy()
    return _config_cache

def invalidate_config_cache():
    """Сбрасывает кэш конфигурации после записи."""
    global _config_cache, _config_mtime
    _config_cache = None
    _config_mtime = 0

# --- Константы для RegisterHotKey ---
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

APP_WINDOW_TITLE = "Click'n'Translate"
SINGLE_INSTANCE_MUTEX_NAME = "ClicknTranslate_SingleInstance_Mutex"
SINGLE_INSTANCE_SHOW_MESSAGE = "ClicknTranslate_ShowWindow_Message"
HWND_BROADCAST = 0xFFFF
ERROR_ALREADY_EXISTS = 183
SW_SHOW = 5
SW_RESTORE = 9

_SHOW_WINDOW_MESSAGE_ID = 0
if sys.platform == "win32":
    try:
        _SHOW_WINDOW_MESSAGE_ID = ctypes.windll.user32.RegisterWindowMessageW(SINGLE_INSTANCE_SHOW_MESSAGE)
    except Exception:
        _SHOW_WINDOW_MESSAGE_ID = 0

_main_window_ref = None
_single_instance_event_filter = None

def _normalize_process_path(path):
    if not path:
        return ""
    try:
        return os.path.normcase(os.path.abspath(path))
    except Exception:
        return os.path.normcase(str(path))


def _current_process_path():
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.executable)
    return os.path.abspath(sys.argv[0])


def _is_clickntranslate_process(process_info):
    exe = process_info.get("exe") or ""
    name = (process_info.get("name") or "").lower()
    exe_name = os.path.basename(exe).lower()
    if exe_name in ("clickntranslate.exe", "clickntranslateapp.exe") or name in ("clickntranslate.exe", "clickntranslateapp.exe"):
        return True
    cmdline = process_info.get("cmdline") or []
    return any(os.path.basename(str(arg)).lower() == "main.py" for arg in cmdline)


def _running_clickntranslate_instances():
    current_pid = os.getpid()
    current_path = _normalize_process_path(_current_process_path())
    instances = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            info = proc.info
            pid = int(info.get("pid") or 0)
            if pid == current_pid or not _is_clickntranslate_process(info):
                continue
            exe_path = info.get("exe") or ""
            if not exe_path:
                cmdline = info.get("cmdline") or []
                exe_path = next((str(arg) for arg in cmdline if str(arg).lower().endswith(".exe")), "")
            instances.append(
                {
                    "pid": pid,
                    "path": exe_path,
                    "same_path": bool(exe_path and _normalize_process_path(exe_path) == current_path),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
            continue
    return instances


def _other_install_instances():
    return [item for item in _running_clickntranslate_instances() if not item["same_path"]]


def _started_from_autostart():
    return "--autostart" in sys.argv


def _confirm_close_other_install(instances):
    if _started_from_autostart():
        return True
    paths = "\n".join(f"- {item.get('path') or 'unknown path'}" for item in instances[:5])
    text = (
        "Click'n'Translate is already running from another folder:\n\n"
        f"{paths}\n\n"
        "Close the old running copy and start this one?"
    )
    try:
        result = ctypes.windll.user32.MessageBoxW(None, text, APP_WINDOW_TITLE, 0x00000004 | 0x00000030)
        return result == 6
    except Exception:
        return False


def _terminate_instances(instances):
    processes = []
    for item in instances:
        try:
            proc = psutil.Process(item["pid"])
            proc.terminate()
            processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    gone, alive = psutil.wait_procs(processes, timeout=5)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            pass


def _show_running_instance():
    """Показать главное окно уже запущенного экземпляра."""
    app = QApplication.instance()
    if app is None:
        return

    target = _main_window_ref
    if target is None:
        for widget in app.topLevelWidgets():
            if hasattr(widget, "show_window_from_tray") and widget.windowTitle() == APP_WINDOW_TITLE:
                target = widget
                break
    if target is None:
        return

    try:
        target.show_window_from_tray(force_show=True)
    except Exception:
        pass

class _SingleInstanceMessageFilter(QtCore.QAbstractNativeEventFilter):
    """Глобальный фильтр системного сообщения активации уже запущенного экземпляра."""
    def nativeEventFilter(self, eventType, message):
        event_name = eventType.decode("utf-8", "ignore") if isinstance(eventType, bytes) else str(eventType)
        if _SHOW_WINDOW_MESSAGE_ID and event_name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == _SHOW_WINDOW_MESSAGE_ID:
                    QTimer.singleShot(0, _show_running_instance)
                    return True, 0
            except Exception:
                pass
        return False, 0

# --- Диспетчер для безопасного вызова UI из потоков хоткеев ---
class _HotkeyDispatcher(QtCore.QObject):
    triggered = QtCore.pyqtSignal(object)

hotkey_dispatcher = _HotkeyDispatcher()

def simulate_copy():
    # Эмуляция нажатия Ctrl+C для копирования выделенного текста
    VK_CONTROL = 0x11
    VK_C = 0x43
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, 0, 0)
    ctypes.windll.user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.02)  # Уменьшено с 0.05 для ускорения
    ctypes.windll.user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    ctypes.windll.user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

def get_app_dir():
    """Directory with app resources (icons, etc). In PyInstaller — temp extraction dir."""
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(sys.argv[0]))

def get_portable_dir():
    """Directory next to the exe for portable data (config, history, cache).
    Settings survive program updates — user just replaces exe/program files."""
    return _portable_base_dir()

def ensure_json_file(filepath, default_content):
    if not os.path.exists(filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=4)

def ensure_data_dir_and_files():
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    config_path = os.path.join(data_dir, "config.json")
    ensure_json_file(config_path, DEFAULT_CONFIG)
    # copy_history.json
    copy_history_path = os.path.join(data_dir, "copy_history.json")
    ensure_json_file(copy_history_path, [])
    # translation_history.json
    translation_history_path = os.path.join(data_dir, "translation_history.json")
    ensure_json_file(translation_history_path, [])
    # settings.json
    settings_path = os.path.join(data_dir, "settings.json")
    ensure_json_file(settings_path, {})

def get_data_file(filename):
    data_dir = os.path.join(get_portable_dir(), "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    file_path = os.path.join(data_dir, filename)
    # Автоматически создаём нужные json-файлы с дефолтным содержимым
    if filename == "config.json":
        ensure_json_file(file_path, DEFAULT_CONFIG)
    elif filename == "copy_history.json":
        ensure_json_file(file_path, [])
    elif filename == "translation_history.json":
        ensure_json_file(file_path, [])
    elif filename == "settings.json":
        ensure_json_file(file_path, {})
    return file_path

def _save_copy_history_sync(text):
    """Синхронная запись в историю копирований (выполняется в отдельном потоке)."""
    try:
        config = get_cached_config()
        if not config.get("copy_history", False):
            return
    except Exception:
        return

    record = {"timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": text}
    history_file = get_data_file("copy_history.json")
    
    history = []
    try:
        if sys.platform == "win32":
            import msvcrt
            with open(history_file, "r+", encoding="utf-8") as f:
                try:
                    f.seek(0, 2)
                    file_size = f.tell()
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, max(file_size, 1))
                except Exception:
                    pass
                try:
                    content = f.read()
                    if content.strip():
                        history = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    history = []
                # Deduplicate consecutive + limit
                if history and history[-1].get("text") == record["text"]:
                    pass  # skip duplicate
                else:
                    history.append(record)
                if len(history) > 500:
                    history = history[-500:]
                f.seek(0)
                f.truncate()
                json.dump(history, f, ensure_ascii=False, indent=4)
                try:
                    f.seek(0, 2)
                    file_size = f.tell()
                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, max(file_size, 1))
                except Exception:
                    pass
        else:
            import fcntl
            with open(history_file, "r+", encoding="utf-8") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    content = f.read()
                    if content.strip():
                        history = json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    history = []
                history.append(record)
                f.seek(0)
                f.truncate()
                json.dump(history, f, ensure_ascii=False, indent=4)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception as e:
        # Fallback без блокировки
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
        if not (history and history[-1].get("text") == record["text"]):
            history.append(record)
        if len(history) > 500:
            history = history[-500:]
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

def save_copy_history(text):
    """Асинхронно сохранить текст в историю копирований (не блокирует UI)."""
    threading.Thread(target=_save_copy_history_sync, args=(text,), daemon=True).start()

# Сигнал для уведомления об ошибке регистрации хоткея
class _HotkeyErrorDispatcher(QtCore.QObject):
    registration_failed = QtCore.pyqtSignal(str)

hotkey_error_dispatcher = _HotkeyErrorDispatcher()

class HotkeyListenerThread(threading.Thread):
    def __init__(self, hotkey_str, callback, hotkey_id=1):
        super().__init__()
        self.hotkey_str = hotkey_str
        self.callback = callback
        self.hotkey_id = hotkey_id
        self.daemon = True  # поток завершается вместе с основным приложением
        self._stop_event = threading.Event()
        self._registered = False
        self.modifiers, self.vk = self.parse_hotkey(self.hotkey_str)
        if self.vk is None:
            print("Неверный формат горячей клавиши.")
    
    def stop(self):
        """Остановить поток и отменить регистрацию горячей клавиши."""
        self._stop_event.set()
        if self._registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
                self._registered = False
            except Exception:
                pass

    def parse_hotkey(self, hotkey_str):
        modifiers = 0
        vk = None
        main_keys = []
        # Маппинг спецсимволов на виртуальные коды Windows
        special_vk = {
            ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF, "`": 0xC0,
            "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
            "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
            "backspace": 0x08, "escape": 0x1B, "esc": 0x1B, "del": 0x2E, "delete": 0x2E,
            "insert": 0x2D, "ins": 0x2D, "home": 0x24, "end": 0x23,
            "pageup": 0x21, "pgup": 0x21, "pagedown": 0x22, "pgdn": 0x22,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "printscreen": 0x2C, "print": 0x2C, "pause": 0x13,
            "numlock": 0x90, "capslock": 0x14, "scrolllock": 0x91
        }
        # Маппинг кириллических букв на латинские эквиваленты (для раскладки)
        cyrillic_to_latin = {
            'й': 'q', 'ц': 'w', 'у': 'e', 'к': 'r', 'е': 't', 'н': 'y', 'г': 'u', 'ш': 'i', 'щ': 'o', 'з': 'p',
            'ф': 'a', 'ы': 's', 'в': 'd', 'а': 'f', 'п': 'g', 'р': 'h', 'о': 'j', 'л': 'k', 'д': 'l',
            'я': 'z', 'ч': 'x', 'с': 'c', 'м': 'v', 'и': 'b', 'т': 'n', 'ь': 'm',
            'х': '[', 'ъ': ']', 'ж': ';', 'э': "'", 'б': ',', 'ю': '.'
        }
        parts = hotkey_str.split("+")
        for part in parts:
            token = part.strip().lower()
            # Преобразуем кириллицу в латиницу для раскладко-независимости
            if len(token) == 1 and token in cyrillic_to_latin:
                token = cyrillic_to_latin[token]
            if token in ("ctrl", "control"):
                modifiers |= MOD_CONTROL
            elif token == "alt":
                modifiers |= MOD_ALT
            elif token == "shift":
                modifiers |= MOD_SHIFT
            elif token in ("win", "meta", "super"):
                modifiers |= MOD_WIN
            elif token in special_vk:
                main_keys.append(special_vk[token])
            elif token.startswith("f") and len(token) > 1 and token[1:].isdigit():
                try:
                    fnum = int(token[1:])
                    if 1 <= fnum <= 24:  # F1-F24
                        main_keys.append(0x70 + fnum - 1)  # VK_F1 = 0x70
                except:
                    pass
            elif len(token) == 1:
                ch = token.upper()
                # ASCII буквы/цифры — VK коды совпадают с ASCII
                if ('A' <= ch <= 'Z') or ('0' <= ch <= '9'):
                    main_keys.append(ord(ch))
                elif ch in special_vk:
                    main_keys.append(special_vk[ch])
                else:
                    # Пытаемся получить VK через WinAPI
                    try:
                        vk_scan = ctypes.windll.user32.VkKeyScanW(ord(ch))
                        if vk_scan != -1 and (vk_scan & 0xFF) != 0xFF:
                            main_keys.append(vk_scan & 0xFF)
                    except Exception:
                        pass
            # иначе игнорируем
        if len(main_keys) == 0:
            print(f"Ошибка: не выбрана основная клавиша для хоткея: {hotkey_str}")
            return modifiers, None
        if len(main_keys) > 1:
            print(f"Ошибка: Windows поддерживает только одну основную клавишу в хоткее! Выбрано: {main_keys}")
            return modifiers, None
        vk = main_keys[0]
        # Добавляем MOD_NOREPEAT для предотвращения повторных срабатываний
        MOD_NOREPEAT = 0x4000
        modifiers |= MOD_NOREPEAT
        return modifiers, vk

    def run(self):
        if self.vk is None:
            print("VK is None, aborting hotkey registration.")
            hotkey_error_dispatcher.registration_failed.emit(self.hotkey_str)
            return
        # Повышаем приоритет текущего потока хоткея для меньшей задержки
        try:
            ctypes.windll.kernel32.SetThreadPriority(ctypes.windll.kernel32.GetCurrentThread(), 2)  # THREAD_PRIORITY_HIGHEST
        except Exception:
            pass
        if not ctypes.windll.user32.RegisterHotKey(None, self.hotkey_id, self.modifiers, self.vk):
            print(f"Failed to register hotkey: {self.hotkey_str}")
            # Эмитируем сигнал об ошибке для UI
            hotkey_error_dispatcher.registration_failed.emit(self.hotkey_str)
            return
        else:
            print(f"Hotkey registered successfully: {self.hotkey_str}")
            self._registered = True

        msg = wintypes.MSG()
        # Используем MsgWaitForMultipleObjects для эффективного ожидания без busy-wait
        QS_ALLINPUT = 0x04FF
        WAIT_TIMEOUT = 258
        INFINITE = 0xFFFFFFFF

        while not self._stop_event.is_set():
            # Ждём сообщения с таймаутом 50ms для проверки stop_event
            result = ctypes.windll.user32.MsgWaitForMultipleObjects(0, None, False, 50, QS_ALLINPUT)

            # Обрабатываем все доступные сообщения
            while ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0x0001):  # PM_REMOVE
                if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
                    try:
                        print(f"Hotkey pressed: {self.hotkey_str}")
                        hotkey_dispatcher.triggered.emit(self.callback)
                    except Exception as e:
                        print(f"Error handling hotkey press: {e}")
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        
        # Отменяем регистрацию при выходе
        if self._registered:
            try:
                ctypes.windll.user32.UnregisterHotKey(None, self.hotkey_id)
                self._registered = False
            except Exception:
                pass

LANGUAGES = {
    code: language_names(code)
    for code in INTERFACE_LANGUAGE_BY_CODE
}

INTERFACE_TEXT = {
    "en": {
        "title": "Click'n'Translate",
        "select_language": "Select languages for translation",
        "start": "Start",
        "translation_selected": "Selected translation: {src} → {tgt}",
        "settings": "Settings",
        "back": "Back to main",
        "ocr": "OCR",
        "help": "Help",
        "choose_interface_language": "Choose interface language",
        "theme": "Change theme",
        "minimize": "Minimize",
        "tray_open": "Open",
        "tray_exit": "Exit",
        "tray_copy": "Copy Text",
        "tray_translate": "Translate",
        "tray_translate_screen": "Translate Screen",
        "input_placeholder": "Enter text to translate",
        "translate_button": "Translate",
        "hotkey_copy": "Copy",
        "hotkey_ocr_translate": "OCR Translate",
        "hotkey_fullscreen": "Fullscreen",
        "hotkey_selection": "Selection",
        "translator": "Translator",
        "shadow_mode": "Shadow mode",
        "copy": "Copy",
        "google": "Google",
        "close": "Close",
        "got_it": "Got it",
        "no_text_selected": "No text selected",
        "translating": "Translating...",
        "translation_error": "Translation error",
        "installing_language_packages": "Installing language packages…"
    },
    "ru": {
        "title": "Click'n'Translate",
        "select_language": "Выберите языки перевода",
        "start": "Старт",
        "translation_selected": "Выбран перевод: {src} → {tgt}",
        "settings": "Настройки",
        "back": "Назад",
        "ocr": "OCR",
        "help": "Помощь",
        "choose_interface_language": "Выбрать язык интерфейса",
        "theme": "Сменить тему",
        "minimize": "Свернуть",
        "tray_open": "Открыть",
        "tray_exit": "Закрыть программу",
        "tray_copy": "Копировать текст",
        "tray_translate": "Перевести",
        "tray_translate_screen": "Перевести экран",
        "input_placeholder": "Введите текст для перевода",
        "translate_button": "Перевести",
        "hotkey_copy": "Копир.",
        "hotkey_ocr_translate": "OCR перевод",
        "hotkey_fullscreen": "Экран",
        "hotkey_selection": "Выделение",
        "translator": "Переводчик",
        "shadow_mode": "Режим тени",
        "copy": "Копировать",
        "google": "Гугл",
        "close": "Закрыть",
        "got_it": "Понятно",
        "no_text_selected": "Текст не выделен",
        "translating": "Переводим...",
        "translation_error": "Ошибка перевода",
        "installing_language_packages": "Установка языковых пакетов…"
    },
    "es": {
        "title": "Click'n'Translate",
        "select_language": "Selecciona idiomas",
        "start": "Iniciar",
        "translation_selected": "Traducción: {src} → {tgt}",
        "settings": "Ajustes",
        "back": "Volver",
        "ocr": "OCR",
        "help": "Ayuda",
        "choose_interface_language": "Elegir idioma de la interfaz",
        "theme": "Cambiar tema",
        "minimize": "Minimizar",
        "tray_open": "Abrir",
        "tray_exit": "Salir",
        "tray_copy": "Copiar texto",
        "tray_translate": "Traducir",
        "tray_translate_screen": "Traducir pantalla",
        "input_placeholder": "Escribe texto para traducir",
        "translate_button": "Traducir",
        "hotkey_copy": "Copiar",
        "hotkey_ocr_translate": "OCR traducir",
        "hotkey_fullscreen": "Pantalla",
        "hotkey_selection": "Selección",
        "translator": "Traductor",
        "shadow_mode": "Modo sombra",
        "copy": "Copiar",
        "google": "Google",
        "close": "Cerrar",
        "got_it": "Entendido",
        "no_text_selected": "No hay texto seleccionado",
        "translating": "Traduciendo...",
        "translation_error": "Error de traducción",
        "installing_language_packages": "Instalando paquetes de idioma…"
    },
    "de": {
        "title": "Click'n'Translate",
        "select_language": "Sprachen wählen",
        "start": "Start",
        "translation_selected": "Übersetzung: {src} → {tgt}",
        "settings": "Einstellungen",
        "back": "Zurück",
        "ocr": "OCR",
        "help": "Hilfe",
        "choose_interface_language": "Sprache der Oberfläche wählen",
        "theme": "Design ändern",
        "minimize": "Minimieren",
        "tray_open": "Öffnen",
        "tray_exit": "Beenden",
        "tray_copy": "Text kopieren",
        "tray_translate": "Übersetzen",
        "tray_translate_screen": "Bildschirm übersetzen",
        "input_placeholder": "Text zum Übersetzen eingeben",
        "translate_button": "Übersetzen",
        "hotkey_copy": "Kopie",
        "hotkey_ocr_translate": "OCR Übers.",
        "hotkey_fullscreen": "Bildschirm",
        "hotkey_selection": "Auswahl",
        "translator": "Übersetzer",
        "shadow_mode": "Schattenmodus",
        "copy": "Kopieren",
        "google": "Google",
        "close": "Schließen",
        "got_it": "Verstanden",
        "no_text_selected": "Kein Text ausgewählt",
        "translating": "Übersetze...",
        "translation_error": "Übersetzungsfehler",
        "installing_language_packages": "Sprachpakete werden installiert…"
    },
    "fr": {
        "title": "Click'n'Translate",
        "select_language": "Choisir les langues",
        "start": "Démarrer",
        "translation_selected": "Traduction : {src} → {tgt}",
        "settings": "Réglages",
        "back": "Retour",
        "ocr": "OCR",
        "help": "Aide",
        "choose_interface_language": "Choisir la langue de l'interface",
        "theme": "Changer de thème",
        "minimize": "Réduire",
        "tray_open": "Ouvrir",
        "tray_exit": "Quitter",
        "tray_copy": "Copier le texte",
        "tray_translate": "Traduire",
        "tray_translate_screen": "Traduire l'écran",
        "input_placeholder": "Saisir le texte à traduire",
        "translate_button": "Traduire",
        "hotkey_copy": "Copier",
        "hotkey_ocr_translate": "OCR traduire",
        "hotkey_fullscreen": "Écran",
        "hotkey_selection": "Sélection",
        "translator": "Traducteur",
        "shadow_mode": "Mode ombre",
        "copy": "Copier",
        "google": "Google",
        "close": "Fermer",
        "got_it": "Compris",
        "no_text_selected": "Aucun texte sélectionné",
        "translating": "Traduction...",
        "translation_error": "Erreur de traduction",
        "installing_language_packages": "Installation des modules de langue…"
    },
    "zh": {
        "title": "Click'n'Translate",
        "select_language": "选择翻译语言",
        "start": "开始",
        "translation_selected": "已选翻译：{src} → {tgt}",
        "settings": "设置",
        "back": "返回",
        "ocr": "OCR",
        "help": "帮助",
        "choose_interface_language": "选择界面语言",
        "theme": "切换主题",
        "minimize": "最小化",
        "tray_open": "打开",
        "tray_exit": "退出",
        "tray_copy": "复制文本",
        "tray_translate": "翻译",
        "tray_translate_screen": "翻译屏幕",
        "input_placeholder": "输入要翻译的文本",
        "translate_button": "翻译",
        "hotkey_copy": "复制",
        "hotkey_ocr_translate": "OCR 翻译",
        "hotkey_fullscreen": "全屏",
        "hotkey_selection": "选区",
        "translator": "翻译器",
        "shadow_mode": "阴影模式",
        "copy": "复制",
        "google": "Google",
        "close": "关闭",
        "got_it": "知道了",
        "no_text_selected": "未选择文本",
        "translating": "正在翻译...",
        "translation_error": "翻译错误",
        "installing_language_packages": "正在安装语言包…"
    }
}


def ui_text(lang, key):
    return INTERFACE_TEXT.get(lang, INTERFACE_TEXT["en"]).get(key, INTERFACE_TEXT["en"].get(key, key))


DOCUMENT_TEXT = {
    "en": {
        "title": "Document translation",
        "main_file_tooltip": "Drop .txt, .md, .docx, .pdf, .html or .rtf here, press Ctrl+O, or right-click the main window.",
        "main_file_hint": "Drop a document here or right-click",
        "attach_file": "Attach file",
        "remove_file": "Remove file",
        "translate_file": "Translate text",
        "translate_selected": "Translate selected",
        "save_translation": "Save translation",
        "open_session": "Open session",
        "context_translate_file": "Choose file to translate",
        "context_choose_folder": "Choose folder with file",
        "source": "Source",
        "target": "Target",
        "auto_detect": "Auto-detect",
        "original": "Original",
        "translated": "Translated",
        "drop_hint": "Type or paste text here, or drop a document.",
        "no_file": "Enter text or attach a file.",
        "loading": "Loading file...",
        "loaded": "Loaded",
        "translating": "Translating",
        "done": "Translation complete",
        "error": "Document translation error",
        "file": "File",
        "size": "Size",
        "detected": "Detected",
        "provider": "Provider",
        "status": "Status",
        "chunks": "Chunks",
        "no_selection": "Select text in the original document first.",
        "no_translation": "There is no translated text to save.",
        "saved": "Saved",
        "session_loaded": "Session loaded",
        "translate_failed": "Translation finished with failed chunks",
        "provider_unavailable_title": "Selected provider is not ready",
        "provider_unavailable_argos": "Argos works offline, but the required local language package is not installed for this language pair. Open Settings, choose Argos and install the needed language package, or choose another provider here.",
        "provider_unavailable_hymt": "Hy-MT works offline, but the local Hy-MT package is not installed. Open Settings, choose Hy-MT and download the offline package, or choose another provider here.",
        "provider_unavailable_online": "This online provider did not return a translation. Check your internet connection or choose another provider here.",
        "provider_unavailable_generic": "Choose another provider here, or open Settings and install the required local package for the selected provider.",
        "technical_error": "Technical error",
    },
    "ru": {
        "title": "Перевод документов",
        "main_file_tooltip": "Перетащите сюда .txt, .md, .docx, .pdf, .html или .rtf, нажмите Ctrl+O или кликните правой кнопкой мыши в главном окне.",
        "main_file_hint": "Перетащите документ сюда или кликните правой кнопкой мыши",
        "attach_file": "Прикрепить файл",
        "remove_file": "Убрать файл",
        "translate_file": "Перевести текст",
        "translate_selected": "Перевести выделение",
        "save_translation": "Сохранить перевод",
        "open_session": "Открыть сессию",
        "context_translate_file": "Выбрать файл для перевода",
        "context_choose_folder": "Выбрать папку с файлом",
        "source": "Исходный",
        "target": "Целевой",
        "auto_detect": "Автоопределение",
        "original": "Оригинал",
        "translated": "Перевод",
        "drop_hint": "Введите или вставьте текст сюда, либо перетащите документ.",
        "no_file": "Введите текст или прикрепите файл.",
        "loading": "Загрузка файла...",
        "loaded": "Загружено",
        "translating": "Перевод",
        "done": "Перевод завершен",
        "error": "Ошибка перевода документа",
        "file": "Файл",
        "size": "Размер",
        "detected": "Определен",
        "provider": "Провайдер",
        "status": "Статус",
        "chunks": "Части",
        "no_selection": "Сначала выделите текст в оригинале.",
        "no_translation": "Нет переведенного текста для сохранения.",
        "saved": "Сохранено",
        "session_loaded": "Сессия загружена",
        "translate_failed": "Перевод завершен с ошибками в частях",
        "provider_unavailable_title": "Выбранный провайдер не готов",
        "provider_unavailable_argos": "Argos работает офлайн, но для этой пары языков не установлен локальный языковой пакет. Откройте настройки, выберите Argos и установите нужный пакет, либо выберите другой провайдер здесь.",
        "provider_unavailable_hymt": "Hy-MT работает офлайн, но локальный пакет Hy-MT не установлен. Откройте настройки, выберите Hy-MT и скачайте офлайн-пакет, либо выберите другой провайдер здесь.",
        "provider_unavailable_online": "Онлайн-провайдер не вернул перевод. Проверьте интернет или выберите другой провайдер здесь.",
        "provider_unavailable_generic": "Выберите другой провайдер здесь, либо откройте настройки и установите нужный локальный пакет для выбранного провайдера.",
        "technical_error": "Техническая ошибка",
    },
    "es": {
        "title": "Traduccion de documentos",
        "main_file_tooltip": "Arrastra aqui .txt, .md, .docx, .pdf, .html o .rtf, pulsa Ctrl+O o haz clic derecho en la ventana principal.",
        "main_file_hint": "Arrastra un documento aqui o haz clic derecho",
        "attach_file": "Adjuntar archivo",
        "remove_file": "Quitar archivo",
        "translate_file": "Traducir texto",
        "translate_selected": "Traducir seleccion",
        "save_translation": "Guardar traduccion",
        "open_session": "Abrir sesion",
        "context_translate_file": "Elegir archivo para traducir",
        "context_choose_folder": "Elegir carpeta con archivo",
        "source": "Origen",
        "target": "Destino",
        "auto_detect": "Detectar auto",
        "original": "Original",
        "translated": "Traducido",
        "drop_hint": "Escribe o pega texto aqui, o arrastra un documento.",
        "no_file": "Introduce texto o adjunta un archivo.",
        "loading": "Cargando archivo...",
        "loaded": "Cargado",
        "translating": "Traduciendo",
        "done": "Traduccion completada",
        "error": "Error de traduccion de documento",
        "file": "Archivo",
        "size": "Tamano",
        "detected": "Detectado",
        "provider": "Proveedor",
        "status": "Estado",
        "chunks": "Partes",
        "no_selection": "Selecciona texto en el documento original.",
        "no_translation": "No hay texto traducido para guardar.",
        "saved": "Guardado",
        "session_loaded": "Sesion cargada",
        "translate_failed": "Traduccion completada con partes fallidas",
        "provider_unavailable_title": "El proveedor elegido no esta listo",
        "provider_unavailable_argos": "Argos funciona offline, pero falta el paquete local para este par de idiomas. Abre Ajustes, elige Argos e instala el paquete necesario, o elige otro proveedor aqui.",
        "provider_unavailable_hymt": "Hy-MT funciona offline, pero el paquete local no esta instalado. Abre Ajustes, elige Hy-MT y descarga el paquete offline, o elige otro proveedor aqui.",
        "provider_unavailable_online": "Este proveedor online no devolvio traduccion. Revisa internet o elige otro proveedor aqui.",
        "provider_unavailable_generic": "Elige otro proveedor aqui, o abre Ajustes e instala el paquete local requerido.",
        "technical_error": "Error tecnico",
    },
    "de": {
        "title": "Dokumentubersetzung",
        "main_file_tooltip": ".txt, .md, .docx, .pdf, .html oder .rtf hier ablegen, Ctrl+O drucken oder im Hauptfenster rechtsklicken.",
        "main_file_hint": "Dokument hier ablegen oder rechtsklicken",
        "attach_file": "Datei anheften",
        "remove_file": "Datei entfernen",
        "translate_file": "Text ubersetzen",
        "translate_selected": "Auswahl ubersetzen",
        "save_translation": "Ubersetzung speichern",
        "open_session": "Sitzung offnen",
        "context_translate_file": "Datei zum Ubersetzen wahlen",
        "context_choose_folder": "Ordner mit Datei wahlen",
        "source": "Quelle",
        "target": "Ziel",
        "auto_detect": "Automatisch",
        "original": "Original",
        "translated": "Ubersetzung",
        "drop_hint": "Text hier eingeben/einfugen oder Dokument ablegen.",
        "no_file": "Text eingeben oder Datei anheften.",
        "loading": "Datei wird geladen...",
        "loaded": "Geladen",
        "translating": "Ubersetze",
        "done": "Ubersetzung abgeschlossen",
        "error": "Fehler bei Dokumentubersetzung",
        "file": "Datei",
        "size": "Grosse",
        "detected": "Erkannt",
        "provider": "Anbieter",
        "status": "Status",
        "chunks": "Teile",
        "no_selection": "Markiere zuerst Text im Original.",
        "no_translation": "Kein ubersetzter Text zum Speichern.",
        "saved": "Gespeichert",
        "session_loaded": "Sitzung geladen",
        "translate_failed": "Ubersetzung mit fehlerhaften Teilen abgeschlossen",
        "provider_unavailable_title": "Der gewahlte Anbieter ist nicht bereit",
        "provider_unavailable_argos": "Argos arbeitet offline, aber das lokale Sprachpaket fur dieses Sprachpaar fehlt. Offne Einstellungen, wahle Argos und installiere das Paket, oder wahle hier einen anderen Anbieter.",
        "provider_unavailable_hymt": "Hy-MT arbeitet offline, aber das lokale Hy-MT-Paket fehlt. Offne Einstellungen, wahle Hy-MT und lade das Offline-Paket, oder wahle hier einen anderen Anbieter.",
        "provider_unavailable_online": "Dieser Online-Anbieter hat keine Ubersetzung geliefert. Prufe die Internetverbindung oder wahle hier einen anderen Anbieter.",
        "provider_unavailable_generic": "Wahle hier einen anderen Anbieter, oder offne Einstellungen und installiere das erforderliche lokale Paket.",
        "technical_error": "Technischer Fehler",
    },
    "fr": {
        "title": "Traduction de documents",
        "main_file_tooltip": "Deposez ici .txt, .md, .docx, .pdf, .html ou .rtf, appuyez sur Ctrl+O ou faites un clic droit dans la fenetre principale.",
        "main_file_hint": "Deposez un document ici ou clic droit",
        "attach_file": "Joindre un fichier",
        "remove_file": "Retirer le fichier",
        "translate_file": "Traduire le texte",
        "translate_selected": "Traduire la selection",
        "save_translation": "Enregistrer",
        "open_session": "Ouvrir session",
        "context_translate_file": "Choisir le fichier a traduire",
        "context_choose_folder": "Choisir le dossier du fichier",
        "source": "Source",
        "target": "Cible",
        "auto_detect": "Detection auto",
        "original": "Original",
        "translated": "Traduction",
        "drop_hint": "Saisissez ou collez du texte ici, ou deposez un document.",
        "no_file": "Saisissez du texte ou joignez un fichier.",
        "loading": "Chargement du fichier...",
        "loaded": "Charge",
        "translating": "Traduction",
        "done": "Traduction terminee",
        "error": "Erreur de traduction du document",
        "file": "Fichier",
        "size": "Taille",
        "detected": "Detecte",
        "provider": "Fournisseur",
        "status": "Etat",
        "chunks": "Parties",
        "no_selection": "Selectionnez d'abord du texte dans l'original.",
        "no_translation": "Aucun texte traduit a enregistrer.",
        "saved": "Enregistre",
        "session_loaded": "Session chargee",
        "translate_failed": "Traduction terminee avec des parties en erreur",
        "provider_unavailable_title": "Le fournisseur choisi n'est pas pret",
        "provider_unavailable_argos": "Argos fonctionne hors ligne, mais le module local manque pour cette paire de langues. Ouvrez les reglages, choisissez Argos et installez le module, ou choisissez un autre fournisseur ici.",
        "provider_unavailable_hymt": "Hy-MT fonctionne hors ligne, mais le paquet local Hy-MT n'est pas installe. Ouvrez les reglages, choisissez Hy-MT et telechargez le paquet offline, ou choisissez un autre fournisseur ici.",
        "provider_unavailable_online": "Ce fournisseur en ligne n'a pas renvoye de traduction. Verifiez internet ou choisissez un autre fournisseur ici.",
        "provider_unavailable_generic": "Choisissez un autre fournisseur ici, ou ouvrez les reglages et installez le paquet local requis.",
        "technical_error": "Erreur technique",
    },
    "zh": {
        "title": "文档翻译",
        "main_file_tooltip": "将 .txt、.md、.docx、.pdf、.html 或 .rtf 拖到这里，按 Ctrl+O，或在主窗口中右键单击。",
        "main_file_hint": "将文档拖到这里或右键单击",
        "attach_file": "附加文件",
        "remove_file": "移除文件",
        "translate_file": "翻译文本",
        "translate_selected": "翻译选中内容",
        "save_translation": "保存翻译",
        "open_session": "打开会话",
        "context_translate_file": "选择要翻译的文件",
        "context_choose_folder": "选择文件所在文件夹",
        "source": "源语言",
        "target": "目标语言",
        "auto_detect": "自动检测",
        "original": "原文",
        "translated": "译文",
        "drop_hint": "在此输入或粘贴文本，或拖入文档。",
        "no_file": "请输入文本或附加文件。",
        "loading": "正在加载文件...",
        "loaded": "已加载",
        "translating": "正在翻译",
        "done": "翻译完成",
        "error": "文档翻译错误",
        "file": "文件",
        "size": "大小",
        "detected": "检测到",
        "provider": "提供商",
        "status": "状态",
        "chunks": "分块",
        "no_selection": "请先在原文中选择文本。",
        "no_translation": "没有可保存的译文。",
        "saved": "已保存",
        "session_loaded": "会话已加载",
        "translate_failed": "翻译完成，但部分分块失败",
        "provider_unavailable_title": "所选提供商尚未就绪",
        "provider_unavailable_argos": "Argos 可离线工作，但当前语言方向缺少本地语言包。请打开设置，选择 Argos 并安装所需语言包，或在这里选择其他提供商。",
        "provider_unavailable_hymt": "Hy-MT 可离线工作，但本地 Hy-MT 包尚未安装。请打开设置，选择 Hy-MT 并下载离线包，或在这里选择其他提供商。",
        "provider_unavailable_online": "该在线提供商没有返回翻译。请检查网络，或在这里选择其他提供商。",
        "provider_unavailable_generic": "请在这里选择其他提供商，或打开设置并安装所选提供商所需的本地包。",
        "technical_error": "技术错误",
    },
}


def doc_text(lang, key):
    text = DOCUMENT_TEXT.get(lang, DOCUMENT_TEXT["en"])
    return text.get(key, DOCUMENT_TEXT["en"].get(key, key))


def document_file_filter():
    extensions = " ".join(f"*{extension}" for extension in sorted(SUPPORTED_EXTENSIONS))
    return f"Documents ({extensions});;All files (*.*)"


TRANSLATION_PROVIDER_OPTIONS = (
    ("google", "Google", "online"),
    ("argos", "Argos", "offline"),
    ("hymt", "Hy-MT", "offline"),
    ("mymemory", "MyMemory", "online"),
    ("lingva", "Lingva", "online"),
    ("libretranslate", "LibreTranslate", "online"),
)


def provider_kind_text(kind, lang):
    if kind == "offline":
        return {
            "ru": "офлайн",
            "es": "offline",
            "de": "offline",
            "fr": "offline",
            "zh": "离线",
        }.get(lang, "offline")
    return {
        "ru": "онлайн",
        "es": "online",
        "de": "online",
        "fr": "online",
        "zh": "在线",
    }.get(lang, "online")


def provider_display_name(engine, lang, include_kind=False):
    engine = str(engine or "google").lower()
    for key, name, kind in TRANSLATION_PROVIDER_OPTIONS:
        if key == engine:
            if include_kind:
                return f"{name} · {provider_kind_text(kind, lang)}"
            return name
    return str(engine or "Google")


def document_translation_icon(theme_name):
    dark = theme_name == "Темная"
    line = QColor("#f7f3ff" if dark else "#1f2937")
    accent = QColor("#c5b3e9" if dark else "#7a5fa1")
    paper_fill = QColor(255, 255, 255, 22) if dark else QColor(122, 95, 161, 16)

    pixmap = QPixmap(30, 30)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(accent, 1.8))
    painter.setBrush(QBrush(paper_fill))
    painter.drawRoundedRect(QtCore.QRectF(6, 4, 16, 22), 3, 3)

    fold = [
        QtCore.QPointF(17, 4),
        QtCore.QPointF(22, 9),
        QtCore.QPointF(17, 9),
    ]
    painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 62)))
    painter.drawPolygon(QPolygonF(fold))

    painter.setPen(QPen(line, 1.2))
    painter.drawLine(QtCore.QPointF(9.5, 13), QtCore.QPointF(18.5, 13))
    painter.drawLine(QtCore.QPointF(9.5, 16.5), QtCore.QPointF(17, 16.5))
    painter.drawLine(QtCore.QPointF(9.5, 20), QtCore.QPointF(14.5, 20))

    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(accent))
    painter.drawRoundedRect(QtCore.QRectF(14, 16, 12, 10), 4, 4)

    painter.setPen(QPen(QColor("#111827" if dark else "#ffffff"), 1))
    font = painter.font()
    font.setPointSize(7)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QtCore.QRectF(14, 16, 12, 10), Qt.AlignCenter, "A")
    painter.end()
    return QIcon(pixmap)


WELCOME_TEXT = {
    "en": {
        "window": "News",
        "eyebrow": "Portable screen translator",
        "title": "Welcome to Click'n'Translate!",
        "body": "We recommend subscribing to the developer's Telegram channel to get updates and news about the program.",
        "feature_ocr": "Screen OCR",
        "feature_translate": "Online + offline",
        "feature_updates": "One-click updates",
        "telegram": "Open Telegram",
        "checkbox": "Don't show this window again",
        "guide": "Show me around",
        "skip": "Skip",
        "close": "Start",
    },
    "ru": {
        "window": "Новости",
        "eyebrow": "Портативный экранный переводчик",
        "title": "Добро пожаловать в Click'n'Translate!",
        "body": "Советуем подписаться на Telegram-канал разработчика, чтобы не пропустить обновления программы и получать свежие новости.",
        "feature_ocr": "OCR с экрана",
        "feature_translate": "Онлайн + офлайн",
        "feature_updates": "Обновление в один клик",
        "telegram": "Открыть Telegram",
        "checkbox": "Больше не показывать это окно",
        "guide": "Пройти обучение",
        "skip": "Пропустить",
        "close": "Начать",
    },
    "es": {
        "window": "Noticias",
        "eyebrow": "Traductor de pantalla portátil",
        "title": "¡Bienvenido a Click'n'Translate!",
        "body": "Te recomendamos suscribirte al canal de Telegram del desarrollador para recibir novedades y actualizaciones.",
        "feature_ocr": "OCR de pantalla",
        "feature_translate": "Online + offline",
        "feature_updates": "Un clic",
        "telegram": "Abrir Telegram",
        "checkbox": "No volver a mostrar esta ventana",
        "guide": "Ver guía",
        "skip": "Omitir",
        "close": "Empezar",
    },
    "de": {
        "window": "Neuigkeiten",
        "eyebrow": "Portabler Bildschirmübersetzer",
        "title": "Willkommen bei Click'n'Translate!",
        "body": "Wir empfehlen, den Telegram-Kanal des Entwicklers zu abonnieren, um Updates und Neuigkeiten zu erhalten.",
        "feature_ocr": "Bildschirm-OCR",
        "feature_translate": "Online + offline",
        "feature_updates": "1-Klick-Update",
        "telegram": "Telegram öffnen",
        "checkbox": "Dieses Fenster nicht mehr anzeigen",
        "guide": "Tour starten",
        "skip": "Überspringen",
        "close": "Starten",
    },
    "fr": {
        "window": "Actualités",
        "eyebrow": "Traducteur d'écran portable",
        "title": "Bienvenue dans Click'n'Translate !",
        "body": "Nous vous conseillons de suivre le canal Telegram du développeur pour recevoir les nouveautés et mises à jour.",
        "feature_ocr": "OCR d'écran",
        "feature_translate": "En ligne + hors ligne",
        "feature_updates": "Un clic",
        "telegram": "Ouvrir Telegram",
        "checkbox": "Ne plus afficher cette fenêtre",
        "guide": "Voir le guide",
        "skip": "Passer",
        "close": "Commencer",
    },
    "zh": {
        "window": "更新",
        "eyebrow": "便携式屏幕翻译器",
        "title": "欢迎使用 Click'n'Translate！",
        "body": "建议订阅开发者的 Telegram 频道，以获取程序更新和最新消息。",
        "feature_ocr": "屏幕 OCR",
        "feature_translate": "在线 + 离线翻译",
        "feature_updates": "一键更新",
        "telegram": "打开 Telegram",
        "checkbox": "不再显示此窗口",
        "guide": "开始引导",
        "skip": "跳过",
        "close": "开始",
    },
}


def welcome_text(lang):
    return WELCOME_TEXT.get(lang, WELCOME_TEXT["en"])


GUIDE_TEXT = {
    "en": {
        "progress": "{current}/{total}",
        "click_hint": "Click glow",
        "skip": "Next",
        "done_title": "Ready",
        "done_body": "You know the main controls now. The full FAQ stays under the info button.",
        "steps": [
            ("language", "Interface language", "Flag changes app, settings, tray and help language."),
            ("theme", "Theme", "Sun/moon switches dark and light themes."),
            ("help", "Help", "Info opens OCR, hotkeys and translator help."),
            ("settings", "Settings", "Gear opens engines, history, updates and hotkeys."),
            ("ocr_engine", "OCR engine", "OCR: Windows is fast; Tesseract works offline."),
            ("translator", "Translator", "Translator: Google online; Argos and Hy-MT offline."),
            ("hotkeys", "Hotkeys", "Hotkeys configure screen copy and OCR translation."),
            ("back_home", "Back home", "Home returns to the main translator screen."),
        ],
    },
    "ru": {
        "progress": "{current}/{total}",
        "click_hint": "Нажми элемент",
        "skip": "Пропустить",
        "done_title": "Готово",
        "done_body": "Готово. Полная справка - под кнопкой информации.",
        "steps": [
            ("language", "Язык интерфейса", "Флаг меняет язык окна, настроек, трея и справки."),
            ("theme", "Тема", "Солнце/луна переключает темную и светлую тему."),
            ("help", "Помощь", "Информация: OCR, хоткеи и переводчики."),
            ("settings", "Настройки", "Шестеренка: движки, история, обновления и хоткеи."),
            ("ocr_engine", "OCR-движок", "OCR: Windows быстрый, Tesseract работает офлайн."),
            ("translator", "Переводчик", "Переводчик: Google онлайн, Argos и Hy-MT офлайн."),
            ("hotkeys", "Горячие клавиши", "Хоткеи: копирование экрана и OCR-перевод."),
            ("back_home", "Назад домой", "Домик возвращает на главный экран."),
        ],
    },
    "es": {
        "progress": "{current}/{total}",
        "click_hint": "Pulsa luz",
        "skip": "Siguiente",
        "done_title": "Listo",
        "done_body": "Ya conoces los controles principales. La guía completa está en el botón de información.",
        "steps": [
            ("language", "Idioma", "Bandera: ventana, ajustes, bandeja y ayuda."),
            ("theme", "Tema", "Sol/luna cambia entre tema oscuro y claro."),
            ("help", "Ayuda", "Info: OCR, atajos y traductores."),
            ("settings", "Ajustes", "Engranaje: motores, historial, updates y atajos."),
            ("ocr_engine", "Motor OCR", "OCR: Windows rápido; Tesseract offline."),
            ("translator", "Traductor", "Traductor: Google online; Argos y Hy-MT offline."),
            ("hotkeys", "Atajos", "Atajos: copia de pantalla y traducción OCR."),
            ("back_home", "Volver", "Casa: vuelve a la pantalla principal."),
        ],
    },
    "de": {
        "progress": "{current}/{total}",
        "click_hint": "Klick Licht",
        "skip": "Weiter",
        "done_title": "Fertig",
        "done_body": "Die wichtigsten Bedienelemente sind bekannt. Die komplette Hilfe bleibt im Info-Button.",
        "steps": [
            ("language", "Sprache", "Flagge: Sprache für App, Tray und Hilfe."),
            ("theme", "Design", "Sonne/Mond wechselt dunkel und hell."),
            ("help", "Hilfe", "Info: OCR, Hotkeys und Übersetzer."),
            ("settings", "Einstellungen", "Zahnrad: Engines, Verlauf, Updates und Hotkeys."),
            ("ocr_engine", "OCR-Engine", "OCR: Windows schnell; Tesseract offline."),
            ("translator", "Übersetzer", "Übersetzer: Google online; Argos/Hy-MT offline."),
            ("hotkeys", "Hotkeys", "Hotkeys: Bildschirmkopie und OCR."),
            ("back_home", "Zurück", "Haus: zurück zum Hauptbildschirm."),
        ],
    },
    "fr": {
        "progress": "{current}/{total}",
        "click_hint": "Clique ici",
        "skip": "Suivant",
        "done_title": "Prêt",
        "done_body": "Les contrôles principaux sont vus. L'aide complète reste dans le bouton info.",
        "steps": [
            ("language", "Langue", "Drapeau: langue de l'app, réglages et aide."),
            ("theme", "Thème", "Soleil/lune alterne sombre et clair."),
            ("help", "Aide", "Info: OCR, raccourcis et traducteurs."),
            ("settings", "Réglages", "Engrenage: moteurs, historique, mises à jour."),
            ("ocr_engine", "Moteur OCR", "OCR: Windows rapide; Tesseract offline."),
            ("translator", "Traducteur", "Traducteur: Google online; Argos/Hy-MT offline."),
            ("hotkeys", "Raccourcis", "Raccourcis: copie écran et OCR."),
            ("back_home", "Retour", "Maison: retour à l'écran principal."),
        ],
    },
    "zh": {
        "progress": "{current}/{total}",
        "click_hint": "点击高亮处",
        "skip": "下一步",
        "done_title": "完成",
        "done_body": "你已经看过主要控件。完整帮助在信息按钮里。",
        "steps": [
            ("language", "界面语言", "点击旗帜。它会切换窗口、设置、托盘和帮助的语言。"),
            ("theme", "主题", "点击太阳/月亮。这里切换深色和浅色主题。"),
            ("help", "帮助", "点击信息按钮。这里有 OCR、快捷键和翻译器说明。"),
            ("settings", "设置", "点击齿轮。引擎、历史、更新和快捷键都在这里。"),
            ("ocr_engine", "OCR 引擎", "打开 OCR。Windows 快且内置；Tesseract 可离线下载。"),
            ("translator", "翻译器", "打开翻译器。Google 在线；Argos 和 Hy-MT 可离线使用。"),
            ("hotkeys", "快捷键", "点击快捷键。这里设置屏幕复制和 OCR 翻译快捷键。"),
            ("back_home", "返回主页", "点击主页图标。它会回到主翻译界面。"),
        ],
    },
}


def guide_text(lang):
    return GUIDE_TEXT.get(lang, GUIDE_TEXT["en"])



_HELP_STYLE = """
<style>
    body { color: #e8e0f7; font-family: "Segoe UI"; }
    .hero {
        background-color: rgba(197, 179, 233, 0.12);
        border: 1px solid rgba(197, 179, 233, 0.45);
        border-radius: 14px;
        padding: 13px;
        margin-bottom: 14px;
    }
    .hero-title { color: #ffffff; font-size: 20px; font-weight: 900; margin-bottom: 6px; }
    .hero-subtitle { color: #cfc4e8; font-size: 13px; line-height: 1.45; }
    .section {
        background-color: rgba(255, 255, 255, 0.045);
        border: 1px solid rgba(197, 179, 233, 0.22);
        border-radius: 13px;
        margin-bottom: 12px;
        padding: 12px;
    }
    .section-title {
        color: #c5b3e9;
        font-size: 16px;
        font-weight: 900;
        margin-bottom: 8px;
    }
    .item { margin: 7px 0; font-size: 13px; line-height: 1.42; }
    .item-title { color: #dfd4ff; font-weight: 900; }
    .recommended { color: #7ee787; font-size: 12px; font-weight: 800; }
    .step {
        background-color: rgba(197, 179, 233, 0.10);
        border-radius: 10px;
        padding: 8px 10px;
        margin: 6px 0;
        font-size: 13px;
    }
    .kbd {
        color: #111827;
        background-color: #c5b3e9;
        border-radius: 7px;
        padding: 2px 6px;
        font-weight: 900;
    }
    .note {
        color: #cfc4e8;
        background-color: rgba(42, 171, 238, 0.10);
        border: 1px solid rgba(42, 171, 238, 0.25);
        border-radius: 10px;
        padding: 9px;
        margin-top: 8px;
    }
</style>
"""

ADDITIONAL_HELP_TEXT = {
    "es": _HELP_STYLE + """
<div class="section"><div class="section-title">🚀 Inicio rápido</div>
<div class="step"><b>1.</b> Pulsa el atajo para copiar o traducir</div>
<div class="step"><b>2.</b> Selecciona el área de la pantalla con texto</div>
<div class="step"><b>3.</b> Elige el idioma del texto en el selector</div>
<div class="step"><b>4.</b> Listo: el texto se copiará o traducirá</div></div>
<div class="section"><div class="section-title">🌐 Traductores</div>
<div class="item"><span class="item-title">Google</span> — rápido y preciso <span class="recommended">✓ Recomendado</span></div>
<div class="item"><span class="item-title">Argos</span> — sin conexión y privado</div>
<div class="item"><span class="item-title">Hy-MT</span> — modelo LLM sin conexión, se instala aparte</div>
<div class="item"><span class="item-title">MyMemory / Lingva / LibreTranslate</span> — proveedores en línea alternativos</div></div>
<div class="section"><div class="section-title">👁 Motores OCR</div>
<div class="item"><span class="item-title">Windows</span> — integrado y rápido <span class="recommended">✓ Recomendado</span></div>
<div class="item"><span class="item-title">Tesseract</span> — sin conexión, preciso, se instala desde ajustes</div></div>
<div class="section"><div class="section-title">⚙️ Ajustes</div>
<div class="item">Configura inicio automático, historial, caché, motores OCR, traductores y atajos.</div>
<div class="item">Si un atajo no funciona, puede estar ocupado por otra aplicación.</div></div>
""",
    "de": _HELP_STYLE + """
<div class="section"><div class="section-title">🚀 Schnellstart</div>
<div class="step"><b>1.</b> Hotkey zum Kopieren oder Übersetzen drücken</div>
<div class="step"><b>2.</b> Bildschirmbereich mit Text markieren</div>
<div class="step"><b>3.</b> Textsprache im Auswahlfeld wählen</div>
<div class="step"><b>4.</b> Fertig: Text wird kopiert oder übersetzt</div></div>
<div class="section"><div class="section-title">🌐 Übersetzer</div>
<div class="item"><span class="item-title">Google</span> — schnell und präzise <span class="recommended">✓ Empfohlen</span></div>
<div class="item"><span class="item-title">Argos</span> — offline und privat</div>
<div class="item"><span class="item-title">Hy-MT</span> — Offline-LLM-Modell, separat installierbar</div>
<div class="item"><span class="item-title">MyMemory / Lingva / LibreTranslate</span> — alternative Online-Anbieter</div></div>
<div class="section"><div class="section-title">👁 OCR-Engines</div>
<div class="item"><span class="item-title">Windows</span> — integriert und schnell <span class="recommended">✓ Empfohlen</span></div>
<div class="item"><span class="item-title">Tesseract</span> — offline, präzise, über Einstellungen installierbar</div></div>
<div class="section"><div class="section-title">⚙️ Einstellungen</div>
<div class="item">Autostart, Verlauf, Cache, OCR-Engines, Übersetzer und Hotkeys werden hier verwaltet.</div>
<div class="item">Wenn ein Hotkey nicht funktioniert, wird er vermutlich von einer anderen App genutzt.</div></div>
""",
    "fr": _HELP_STYLE + """
<div class="section"><div class="section-title">🚀 Démarrage rapide</div>
<div class="step"><b>1.</b> Appuyez sur le raccourci pour copier ou traduire</div>
<div class="step"><b>2.</b> Sélectionnez la zone de l'écran contenant du texte</div>
<div class="step"><b>3.</b> Choisissez la langue du texte dans le sélecteur</div>
<div class="step"><b>4.</b> Terminé : le texte est copié ou traduit</div></div>
<div class="section"><div class="section-title">🌐 Traducteurs</div>
<div class="item"><span class="item-title">Google</span> — rapide et précis <span class="recommended">✓ Recommandé</span></div>
<div class="item"><span class="item-title">Argos</span> — hors ligne et privé</div>
<div class="item"><span class="item-title">Hy-MT</span> — modèle LLM hors ligne, installé séparément</div>
<div class="item"><span class="item-title">MyMemory / Lingva / LibreTranslate</span> — fournisseurs en ligne alternatifs</div></div>
<div class="section"><div class="section-title">👁 Moteurs OCR</div>
<div class="item"><span class="item-title">Windows</span> — intégré et rapide <span class="recommended">✓ Recommandé</span></div>
<div class="item"><span class="item-title">Tesseract</span> — hors ligne, précis, installable depuis les réglages</div></div>
<div class="section"><div class="section-title">⚙️ Réglages</div>
<div class="item">Gérez le démarrage automatique, l'historique, le cache, les moteurs OCR, les traducteurs et les raccourcis.</div>
<div class="item">Si un raccourci ne fonctionne pas, il est peut-être utilisé par une autre application.</div></div>
""",
    "zh": _HELP_STYLE + """
<div class="section"><div class="section-title">🚀 快速开始</div>
<div class="step"><b>1.</b> 按复制或翻译快捷键</div>
<div class="step"><b>2.</b> 用鼠标选择屏幕上的文本区域</div>
<div class="step"><b>3.</b> 在选择器中选择文本语言</div>
<div class="step"><b>4.</b> 完成：文本会被复制或翻译</div></div>
<div class="section"><div class="section-title">🌐 翻译器</div>
<div class="item"><span class="item-title">Google</span> — 快速且准确 <span class="recommended">✓ 推荐</span></div>
<div class="item"><span class="item-title">Argos</span> — 离线、私密</div>
<div class="item"><span class="item-title">Hy-MT</span> — 离线 LLM 模型，需要单独安装</div>
<div class="item"><span class="item-title">MyMemory / Lingva / LibreTranslate</span> — 其他在线提供商</div></div>
<div class="section"><div class="section-title">👁 OCR 引擎</div>
<div class="item"><span class="item-title">Windows</span> — 系统内置，速度快 <span class="recommended">✓ 推荐</span></div>
<div class="item"><span class="item-title">Tesseract</span> — 离线、准确，可在设置中安装</div></div>
<div class="section"><div class="section-title">⚙️ 设置</div>
<div class="item">这里可以管理自动启动、历史记录、缓存、OCR 引擎、翻译器和快捷键。</div>
<div class="item">如果快捷键不起作用，可能已被其他应用占用。</div></div>
""",
}

HELP_CONTENT = {
    "en": [
        ("Quick Start", [
            "<b>1.</b> Press the copy or translate hotkey.",
            "<b>2.</b> Select the screen area that contains text.",
            "<b>3.</b> Choose the OCR/source language from the flag selector when needed.",
            "<b>4.</b> The app copies recognized text or shows the translation.",
        ]),
        ("Interface Language", [
            "Use the flag button in the title bar to switch the interface language.",
            "The main window, settings, hotkeys, history screens, tray menu and this FAQ follow the selected language.",
            "OCR and translation language selection is separate from the interface language.",
        ]),
        ("Translators", [
            "<span class='item-title'>Google</span> - fast online translation, recommended by default.",
            "<span class='item-title'>Argos</span> - offline and private, requires local language packages.",
            "<span class='item-title'>Hy-MT</span> - local LLM translation package, installed separately from Settings.",
            "<span class='item-title'>MyMemory, Lingva, LibreTranslate</span> - alternative online providers.",
        ]),
        ("OCR Engines", [
            "<span class='item-title'>Windows</span> - built into Windows, fast, depends on installed Windows language packs.",
            "<span class='item-title'>Tesseract</span> - offline OCR engine; Settings can download a local portable package.",
            "<span class='item-title'>AUTO</span> cannot know the language before OCR. With Windows OCR it tries installed OCR languages and selects the most readable result.",
            "If the needed language is not installed in Windows OCR, install its Windows language pack, choose a specific language, or use Tesseract.",
        ]),
        ("Settings", [
            "Shadow mode starts the app hidden in the system tray.",
            "Keep window visible prevents the main window from hiding during OCR capture.",
            "Freeze screen makes selecting moving text easier.",
            "History and cache can be enabled, viewed, and cleared from Settings.",
        ]),
        ("Hotkeys", [
            "<span class='item-title'>Copy</span> recognizes the selected area and copies text.",
            "<span class='item-title'>OCR Translate</span> recognizes the selected area and translates it.",
            "<span class='item-title'>Fullscreen</span> translates visible text blocks on the screen.",
            "<span class='item-title'>Selection</span> translates the currently selected text from another app.",
        ]),
        ("Portable App", [
            "The app stores config, history, cache and optional local engines next to the program folder.",
            "Move the folder to its final location before enabling autostart or creating shortcuts.",
        ]),
    ],
    "ru": [
        ("Быстрый старт", [
            "<b>1.</b> Нажмите горячую клавишу копирования или перевода.",
            "<b>2.</b> Выделите область экрана с текстом.",
            "<b>3.</b> При необходимости выберите язык OCR/исходного текста через флаг.",
            "<b>4.</b> Программа скопирует распознанный текст или покажет перевод.",
        ]),
        ("Язык интерфейса", [
            "Кнопка с флагом в заголовке переключает язык интерфейса.",
            "Главное окно, настройки, горячие клавиши, история, меню трея и этот FAQ следуют выбранному языку.",
            "Язык интерфейса не меняет язык OCR и направление перевода: они настраиваются отдельно.",
        ]),
        ("Переводчики", [
            "<span class='item-title'>Google</span> - быстрый онлайн-перевод, выбран по умолчанию.",
            "<span class='item-title'>Argos</span> - офлайн и приватно, нужны локальные языковые пакеты.",
            "<span class='item-title'>Hy-MT</span> - локальный LLM-пакет перевода, устанавливается отдельно из настроек.",
            "<span class='item-title'>MyMemory, Lingva, LibreTranslate</span> - альтернативные онлайн-провайдеры.",
        ]),
        ("OCR-движки", [
            "<span class='item-title'>Windows</span> - встроен в Windows, быстрый, зависит от установленных языковых пакетов Windows.",
            "<span class='item-title'>Tesseract</span> - офлайн OCR; настройки умеют скачать локальный portable-пакет.",
            "<span class='item-title'>AUTO</span> не может узнать язык до OCR, потому что текста еще нет. В Windows OCR он пробует установленные OCR-языки и выбирает самый читаемый результат.",
            "Если нужный язык не установлен в Windows OCR, установите языковой пакет Windows, выберите язык вручную или используйте Tesseract.",
        ]),
        ("Настройки", [
            "Режим тени запускает программу скрытой в системном трее.",
            "Не сворачивать при OCR оставляет главное окно видимым во время захвата.",
            "Заморозка экрана помогает выделять движущийся текст.",
            "Историю и кэш можно включать, просматривать и очищать в настройках.",
        ]),
        ("Горячие клавиши", [
            "<span class='item-title'>Копирование</span> распознает выделенную область и копирует текст.",
            "<span class='item-title'>OCR-перевод</span> распознает выделенную область и переводит ее.",
            "<span class='item-title'>Экран</span> переводит видимые текстовые блоки на экране.",
            "<span class='item-title'>Выделение</span> переводит уже выделенный текст из другого приложения.",
        ]),
        ("Портативность", [
            "Конфиг, история, кэш и локальные движки хранятся рядом с папкой программы.",
            "Переместите папку в постоянное место до включения автозапуска или создания ярлыков.",
        ]),
    ],
    "es": [
        ("Inicio rapido", [
            "<b>1.</b> Pulsa el atajo de copiar o traducir.",
            "<b>2.</b> Selecciona el area de la pantalla con texto.",
            "<b>3.</b> Elige el idioma OCR/origen con la bandera cuando haga falta.",
            "<b>4.</b> La app copia el texto reconocido o muestra la traduccion.",
        ]),
        ("Idioma de la interfaz", [
            "El boton de bandera en la barra superior cambia el idioma de la interfaz.",
            "Ventana principal, ajustes, atajos, historiales, menu de bandeja y este FAQ usan el idioma elegido.",
            "El idioma de interfaz no cambia el idioma OCR ni la direccion de traduccion.",
        ]),
        ("Traductores", [
            "<span class='item-title'>Google</span> - traduccion online rapida, recomendada por defecto.",
            "<span class='item-title'>Argos</span> - sin conexion y privado; requiere paquetes locales.",
            "<span class='item-title'>Hy-MT</span> - paquete LLM local, se instala aparte desde Ajustes.",
            "<span class='item-title'>MyMemory, Lingva, LibreTranslate</span> - proveedores online alternativos.",
        ]),
        ("Motores OCR", [
            "<span class='item-title'>Windows</span> - integrado en Windows, rapido, depende de paquetes de idioma instalados.",
            "<span class='item-title'>Tesseract</span> - OCR sin conexion; Ajustes puede descargar un paquete portable.",
            "<span class='item-title'>AUTO</span> no puede saber el idioma antes del OCR. Con Windows OCR prueba los idiomas OCR instalados y elige el resultado mas legible.",
            "Si el idioma necesario no esta instalado en Windows OCR, instala su paquete de idioma de Windows, elige un idioma concreto o usa Tesseract.",
        ]),
        ("Ajustes", [
            "Modo sombra inicia la app oculta en la bandeja del sistema.",
            "Mantener ventana visible evita ocultar la ventana principal durante OCR.",
            "Congelar pantalla ayuda a seleccionar texto en movimiento.",
            "El historial y la cache se pueden activar, ver y limpiar desde Ajustes.",
        ]),
        ("Atajos", [
            "<span class='item-title'>Copiar</span> reconoce el area seleccionada y copia el texto.",
            "<span class='item-title'>OCR traducir</span> reconoce el area seleccionada y la traduce.",
            "<span class='item-title'>Pantalla</span> traduce bloques de texto visibles en pantalla.",
            "<span class='item-title'>Seleccion</span> traduce texto ya seleccionado en otra app.",
        ]),
        ("Portabilidad", [
            "Config, historial, cache y motores locales se guardan junto a la carpeta del programa.",
            "Mueve la carpeta a su ubicacion final antes de activar inicio automatico o crear accesos directos.",
        ]),
    ],
    "de": [
        ("Schnellstart", [
            "<b>1.</b> Drucken Sie das Kopieren- oder Ubersetzen-Tastenkurzel.",
            "<b>2.</b> Markieren Sie den Bildschirmbereich mit Text.",
            "<b>3.</b> Wahlen Sie bei Bedarf die OCR-/Quellsprache uber die Flagge.",
            "<b>4.</b> Die App kopiert erkannten Text oder zeigt die Ubersetzung.",
        ]),
        ("Sprache der Oberflache", [
            "Die Flagge in der Titelleiste wechselt die Sprache der Oberflache.",
            "Hauptfenster, Einstellungen, Tastenkurzel, Verlauf, Tray-Menu und dieses FAQ folgen der gewahlten Sprache.",
            "Die Oberflachensprache andert OCR-Sprache und Ubersetzungsrichtung nicht.",
        ]),
        ("Ubersetzer", [
            "<span class='item-title'>Google</span> - schnelle Online-Ubersetzung, standardmassig empfohlen.",
            "<span class='item-title'>Argos</span> - offline und privat; lokale Sprachpakete erforderlich.",
            "<span class='item-title'>Hy-MT</span> - lokales LLM-Paket, separat in den Einstellungen installierbar.",
            "<span class='item-title'>MyMemory, Lingva, LibreTranslate</span> - alternative Online-Anbieter.",
        ]),
        ("OCR-Engines", [
            "<span class='item-title'>Windows</span> - in Windows integriert, schnell, hangt von installierten Sprachpaketen ab.",
            "<span class='item-title'>Tesseract</span> - Offline-OCR; Einstellungen konnen ein portables Paket laden.",
            "<span class='item-title'>AUTO</span> kann die Sprache nicht vor der OCR kennen. Mit Windows OCR werden installierte OCR-Sprachen getestet und das lesbarste Ergebnis gewahlt.",
            "Wenn die benotigte Sprache in Windows OCR fehlt, installiere das Windows-Sprachpaket, wahle eine konkrete Sprache oder nutze Tesseract.",
        ]),
        ("Einstellungen", [
            "Schattenmodus startet die App ausgeblendet im System-Tray.",
            "Fenster sichtbar halten verhindert, dass das Hauptfenster beim OCR ausgeblendet wird.",
            "Bildschirm einfrieren hilft beim Markieren bewegter Texte.",
            "Verlauf und Cache konnen in den Einstellungen aktiviert, angezeigt und geleert werden.",
        ]),
        ("Tastenkurzel", [
            "<span class='item-title'>Kopieren</span> erkennt den markierten Bereich und kopiert Text.",
            "<span class='item-title'>OCR-Ubersetzen</span> erkennt den markierten Bereich und ubersetzt ihn.",
            "<span class='item-title'>Bildschirm</span> ubersetzt sichtbare Textblocke auf dem Bildschirm.",
            "<span class='item-title'>Auswahl</span> ubersetzt bereits markierten Text aus einer anderen App.",
        ]),
        ("Portabilitat", [
            "Konfig, Verlauf, Cache und lokale Engines liegen neben dem Programmordner.",
            "Verschieben Sie den Ordner an seinen endgultigen Ort, bevor Autostart oder Verknupfungen erstellt werden.",
        ]),
    ],
    "fr": [
        ("Demarrage rapide", [
            "<b>1.</b> Appuyez sur le raccourci de copie ou de traduction.",
            "<b>2.</b> Selectionnez la zone de l'ecran contenant du texte.",
            "<b>3.</b> Choisissez la langue OCR/source avec le drapeau si besoin.",
            "<b>4.</b> L'app copie le texte reconnu ou affiche la traduction.",
        ]),
        ("Langue de l'interface", [
            "Le bouton drapeau dans la barre de titre change la langue de l'interface.",
            "Fenetre principale, reglages, raccourcis, historiques, menu de zone de notification et ce FAQ suivent la langue choisie.",
            "La langue de l'interface ne change pas la langue OCR ni le sens de traduction.",
        ]),
        ("Traducteurs", [
            "<span class='item-title'>Google</span> - traduction en ligne rapide, recommandee par defaut.",
            "<span class='item-title'>Argos</span> - hors ligne et prive; modules locaux requis.",
            "<span class='item-title'>Hy-MT</span> - paquet LLM local, installe separement depuis les reglages.",
            "<span class='item-title'>MyMemory, Lingva, LibreTranslate</span> - fournisseurs en ligne alternatifs.",
        ]),
        ("Moteurs OCR", [
            "<span class='item-title'>Windows</span> - integre a Windows, rapide, depend des modules de langue installes.",
            "<span class='item-title'>Tesseract</span> - OCR hors ligne; les reglages peuvent telecharger un paquet portable.",
            "<span class='item-title'>AUTO</span> ne peut pas connaitre la langue avant l'OCR. Avec Windows OCR, il teste les langues OCR installees et choisit le resultat le plus lisible.",
            "Si la langue requise manque dans Windows OCR, installe le module de langue Windows, choisis une langue precise ou utilise Tesseract.",
        ]),
        ("Reglages", [
            "Mode ombre lance l'app cachee dans la zone de notification.",
            "Garder la fenetre visible empeche de masquer la fenetre principale pendant l'OCR.",
            "Figer l'ecran facilite la selection de texte en mouvement.",
            "Historique et cache peuvent etre actives, consultes et nettoyes dans les reglages.",
        ]),
        ("Raccourcis", [
            "<span class='item-title'>Copier</span> reconnait la zone selectionnee et copie le texte.",
            "<span class='item-title'>OCR traduire</span> reconnait la zone selectionnee et la traduit.",
            "<span class='item-title'>Plein ecran</span> traduit les blocs de texte visibles a l'ecran.",
            "<span class='item-title'>Selection</span> traduit le texte deja selectionne dans une autre app.",
        ]),
        ("Portabilite", [
            "Config, historique, cache et moteurs locaux sont stockes a cote du dossier du programme.",
            "Deplacez le dossier a son emplacement final avant d'activer le demarrage automatique ou de creer des raccourcis.",
        ]),
    ],
    "zh": [
        ("快速开始", [
            "<b>1.</b> 按复制或翻译快捷键。",
            "<b>2.</b> 选择屏幕上包含文字的区域。",
            "<b>3.</b> 需要时通过旗帜选择 OCR/源语言。",
            "<b>4.</b> 应用会复制识别文本或显示翻译。",
        ]),
        ("界面语言", [
            "标题栏的旗帜按钮用于切换界面语言。",
            "主窗口、设置、快捷键、历史记录、托盘菜单和本 FAQ 都会跟随所选语言。",
            "界面语言不会改变 OCR 语言或翻译方向，这些需要单独设置。",
        ]),
        ("翻译器", [
            "<span class='item-title'>Google</span> - 快速在线翻译，默认推荐。",
            "<span class='item-title'>Argos</span> - 离线且私密，需要本地语言包。",
            "<span class='item-title'>Hy-MT</span> - 本地 LLM 翻译包，可在设置中单独安装。",
            "<span class='item-title'>MyMemory, Lingva, LibreTranslate</span> - 其他在线翻译服务。",
        ]),
        ("OCR 引擎", [
            "<span class='item-title'>Windows</span> - Windows 内置，速度快，依赖已安装的 Windows 语言包。",
            "<span class='item-title'>Tesseract</span> - 离线 OCR；设置中可以下载本地便携包。",
            "<span class='item-title'>AUTO</span> 无法在 OCR 前知道语言，因为文字还没有被识别。使用 Windows OCR 时，它会尝试已安装的 OCR 语言并选择最可读的结果。",
            "如果 Windows OCR 没有所需语言，请安装对应 Windows 语言包、手动选择语言，或使用 Tesseract。",
        ]),
        ("设置", [
            "阴影模式会让应用启动后隐藏在系统托盘。",
            "OCR 时保持窗口可见会防止主窗口在截图时隐藏。",
            "冻结屏幕有助于选择正在变化的文字。",
            "历史记录和缓存可以在设置中启用、查看和清除。",
        ]),
        ("快捷键", [
            "<span class='item-title'>复制</span> 识别所选区域并复制文本。",
            "<span class='item-title'>OCR 翻译</span> 识别所选区域并翻译。",
            "<span class='item-title'>全屏</span> 翻译屏幕上可见的文本块。",
            "<span class='item-title'>选区</span> 翻译其他应用中已选中的文本。",
        ]),
        ("便携应用", [
            "配置、历史、缓存和本地引擎都保存在程序文件夹旁边。",
            "启用自启动或创建快捷方式前，请先把程序文件夹移动到最终位置。",
        ]),
    ],
}


HELP_INTRO = {
    "en": (
        "Click'n'Translate is a portable assistant for screen OCR, quick translation, hotkeys and optional offline engines. "
        "Use this FAQ as a map; the interactive guide can be launched again from the button below."
    ),
    "ru": (
        "Click'n'Translate - портативный помощник для OCR с экрана, быстрого перевода, горячих клавиш и офлайн-движков. "
        "Этот FAQ работает как карта программы; интерактивное обучение можно снова запустить кнопкой ниже."
    ),
    "es": (
        "Click'n'Translate es un asistente portátil para OCR de pantalla, traducción rápida, atajos y motores offline opcionales. "
        "Este FAQ sirve como mapa; la guía interactiva se puede abrir de nuevo con el botón inferior."
    ),
    "de": (
        "Click'n'Translate ist ein portabler Assistent für Bildschirm-OCR, schnelle Übersetzung, Hotkeys und optionale Offline-Engines. "
        "Diese FAQ ist die Karte; die interaktive Tour kann unten erneut gestartet werden."
    ),
    "fr": (
        "Click'n'Translate est un assistant portable pour OCR d'écran, traduction rapide, raccourcis et moteurs offline optionnels. "
        "Cette FAQ sert de carte; le guide interactif peut être relancé avec le bouton en bas."
    ),
    "zh": (
        "Click'n'Translate 是便携式屏幕 OCR、快速翻译、快捷键和可选离线引擎助手。"
        "这份 FAQ 是功能地图；底部按钮可以重新启动交互式引导。"
    ),
}

HELP_EXTRA_CONTENT = {
    "en": [
        ("Best OCR results", [
            "Select only the text area, not the whole window. Smaller captures are faster and cleaner.",
            "Use <span class='item-title'>Freeze screen during OCR</span> when the source moves, fades, or disappears.",
            "If Windows OCR misses a language, try Tesseract or install the needed Windows language pack.",
        ]),
        ("Offline packages", [
            "<span class='item-title'>Tesseract</span> adds offline OCR and many recognition languages.",
            "<span class='item-title'>Argos</span> is offline translation with small language packages.",
            "<span class='item-title'>Hy-MT</span> is a larger local model; install it only when you need offline quality and have disk space.",
        ]),
        ("Updates and portable mode", [
            "The update button downloads the release archive and replaces the portable folder automatically.",
            "Keep the app in a stable folder before enabling autostart, otherwise Windows may point to the old path.",
            "Config, cache, history and local engines live in the program data folder so the app can move as one package.",
        ]),
        ("Privacy", [
            "Online providers send text to their service. Use Argos, Hy-MT and Tesseract when you need local-only work.",
            "History and copy history are optional; turn them off if you do not want text stored locally.",
        ]),
    ],
    "ru": [
        ("Как получить точный OCR", [
            "Выделяй только область с текстом, а не всё окно. Маленький захват быстрее и чище.",
            "Включай <span class='item-title'>Заморозку экрана при OCR</span>, если текст движется, пропадает или меняется.",
            "Если Windows OCR не видит язык, попробуй Tesseract или установи нужный языковой пакет Windows.",
        ]),
        ("Офлайн-пакеты", [
            "<span class='item-title'>Tesseract</span> добавляет офлайн OCR и много языков распознавания.",
            "<span class='item-title'>Argos</span> даёт офлайн-перевод через небольшие языковые пакеты.",
            "<span class='item-title'>Hy-MT</span> - крупная локальная модель; ставь её, когда нужна офлайн-точность и есть место на диске.",
        ]),
        ("Обновления и portable-режим", [
            "Кнопка обновления скачивает архив релиза и автоматически заменяет portable-папку.",
            "Перед автозапуском положи программу в постоянную папку, иначе Windows может помнить старый путь.",
            "Конфиг, кэш, история и локальные движки лежат в папке данных программы, поэтому её можно переносить целиком.",
        ]),
        ("Приватность", [
            "Онлайн-провайдеры отправляют текст в свой сервис. Для локальной работы используй Argos, Hy-MT и Tesseract.",
            "История переводов и копирования необязательны; отключи их, если не хочешь хранить текст локально.",
        ]),
    ],
    "es": [
        ("Mejor OCR", [
            "Selecciona solo el área con texto, no toda la ventana.",
            "Usa <span class='item-title'>Congelar pantalla durante OCR</span> si el texto se mueve o desaparece.",
            "Si Windows OCR no reconoce un idioma, prueba Tesseract o instala el paquete de idioma de Windows.",
        ]),
        ("Paquetes offline", [
            "<span class='item-title'>Tesseract</span> agrega OCR offline y muchos idiomas.",
            "<span class='item-title'>Argos</span> traduce offline con paquetes pequeños.",
            "<span class='item-title'>Hy-MT</span> es un modelo local más grande para mejor calidad offline.",
        ]),
        ("Actualizaciones y modo portátil", [
            "El botón de actualización descarga el release y reemplaza la carpeta portable.",
            "Coloca la app en una carpeta fija antes de activar inicio automático.",
            "Config, caché, historial y motores locales viven junto a la app.",
        ]),
        ("Privacidad", [
            "Los proveedores online reciben el texto. Para trabajo local usa Argos, Hy-MT y Tesseract.",
            "El historial es opcional; desactívalo si no quieres guardar texto localmente.",
        ]),
    ],
    "de": [
        ("Bessere OCR-Ergebnisse", [
            "Markiere nur den Textbereich, nicht das ganze Fenster.",
            "Nutze <span class='item-title'>Bildschirm einfrieren</span>, wenn Text sich bewegt oder verschwindet.",
            "Wenn Windows OCR eine Sprache nicht erkennt, nutze Tesseract oder installiere das Windows-Sprachpaket.",
        ]),
        ("Offline-Pakete", [
            "<span class='item-title'>Tesseract</span> ergänzt Offline-OCR und viele Sprachen.",
            "<span class='item-title'>Argos</span> übersetzt offline mit kleinen Sprachpaketen.",
            "<span class='item-title'>Hy-MT</span> ist ein größeres lokales Modell für bessere Offline-Qualität.",
        ]),
        ("Updates und Portable-Modus", [
            "Der Update-Button lädt das Release und ersetzt den portablen Ordner.",
            "Lege die App vor Autostart in einen festen Ordner.",
            "Konfig, Cache, Verlauf und lokale Engines liegen neben der App.",
        ]),
        ("Datenschutz", [
            "Online-Anbieter erhalten den Text. Für lokale Arbeit nutze Argos, Hy-MT und Tesseract.",
            "Verlauf ist optional; ausschalten, wenn lokal nichts gespeichert werden soll.",
        ]),
    ],
    "fr": [
        ("Meilleur OCR", [
            "Sélectionne seulement la zone de texte, pas toute la fenêtre.",
            "Utilise <span class='item-title'>Figer l'écran pendant l'OCR</span> si le texte bouge ou disparaît.",
            "Si Windows OCR ne reconnaît pas une langue, essaie Tesseract ou installe le module Windows.",
        ]),
        ("Modules offline", [
            "<span class='item-title'>Tesseract</span> ajoute OCR offline et beaucoup de langues.",
            "<span class='item-title'>Argos</span> traduit offline avec de petits modules.",
            "<span class='item-title'>Hy-MT</span> est un modèle local plus grand pour meilleure qualité offline.",
        ]),
        ("Mises à jour et mode portable", [
            "Le bouton de mise à jour télécharge le release et remplace le dossier portable.",
            "Place l'app dans un dossier stable avant d'activer le démarrage automatique.",
            "Config, cache, historique et moteurs locaux restent à côté de l'app.",
        ]),
        ("Confidentialité", [
            "Les fournisseurs en ligne reçoivent le texte. Pour rester local, utilise Argos, Hy-MT et Tesseract.",
            "L'historique est optionnel; désactive-le si tu ne veux rien stocker localement.",
        ]),
    ],
    "zh": [
        ("提升 OCR 准确率", [
            "只选择文字区域，不要截取整个窗口。",
            "如果文字会移动或消失，请使用 <span class='item-title'>OCR 时冻结屏幕</span>。",
            "如果 Windows OCR 缺少语言，请尝试 Tesseract 或安装 Windows 语言包。",
        ]),
        ("离线包", [
            "<span class='item-title'>Tesseract</span> 提供离线 OCR 和多语言识别。",
            "<span class='item-title'>Argos</span> 使用小型语言包进行离线翻译。",
            "<span class='item-title'>Hy-MT</span> 是更大的本地模型，适合需要离线质量时使用。",
        ]),
        ("更新和便携模式", [
            "更新按钮会下载 release 压缩包并替换便携文件夹。",
            "启用自启动前，请把程序放到固定位置。",
            "配置、缓存、历史和本地引擎都保存在程序数据目录中。",
        ]),
        ("隐私", [
            "在线提供商会接收文本。需要本地处理时请使用 Argos、Hy-MT 和 Tesseract。",
            "历史记录是可选的；如果不想本地保存文本，可以关闭。",
        ]),
    ],
}

DOCUMENT_HELP_CONTENT = {
    "en": [
        ("Document translation", [
            "Drop a .txt, .md, .docx, .pdf, .html or .rtf file onto the main window, or press Ctrl+O.",
            "The document reader can translate the whole file or only selected text.",
            "Long files are split into ordered chunks; failed chunks stay visible in the result.",
            "Translations can be saved locally as .txt, .md or a reopenable session in the program data folder.",
        ]),
    ],
    "ru": [
        ("Перевод документов", [
            "Перетащите .txt, .md, .docx, .pdf, .html или .rtf в главное окно, либо нажмите Ctrl+O.",
            "Окно документа умеет переводить весь файл или только выделенный текст.",
            "Длинные файлы режутся на части по порядку; ошибки отдельных частей остаются видимыми в результате.",
            "Перевод можно сохранить локально как .txt, .md или сессию для повторного открытия.",
        ]),
    ],
    "es": [
        ("Traduccion de documentos", [
            "Arrastra .txt, .md, .docx, .pdf, .html o .rtf a la ventana principal, o pulsa Ctrl+O.",
            "El lector puede traducir todo el archivo o solo el texto seleccionado.",
            "Los archivos largos se dividen en partes ordenadas; las partes fallidas quedan visibles.",
            "La traduccion se guarda localmente como .txt, .md o sesion reutilizable.",
        ]),
    ],
    "de": [
        ("Dokumentubersetzung", [
            ".txt, .md, .docx, .pdf, .html oder .rtf ins Hauptfenster ziehen oder Ctrl+O drucken.",
            "Der Dokumentreader ubersetzt die ganze Datei oder nur markierten Text.",
            "Lange Dateien werden in geordnete Teile geteilt; fehlgeschlagene Teile bleiben sichtbar.",
            "Ubersetzungen werden lokal als .txt, .md oder wieder offnbare Sitzung gespeichert.",
        ]),
    ],
    "fr": [
        ("Traduction de documents", [
            "Deposez .txt, .md, .docx, .pdf, .html ou .rtf dans la fenetre principale, ou appuyez sur Ctrl+O.",
            "Le lecteur peut traduire tout le fichier ou seulement le texte selectionne.",
            "Les longs fichiers sont decoupes en parties ordonnees; les erreurs restent visibles.",
            "La traduction se sauvegarde localement en .txt, .md ou session reutilisable.",
        ]),
    ],
    "zh": [
        ("文档翻译", [
            "将 .txt、.md、.docx、.pdf、.html 或 .rtf 拖到主窗口，或按 Ctrl+O。",
            "文档阅读器可以翻译整个文件，也可以只翻译选中的文本。",
            "长文件会按顺序分块翻译；失败的分块会保留在结果中。",
            "译文可本地保存为 .txt、.md 或可重新打开的会话。",
        ]),
    ],
}


HELP_ACTION_TEXT = {
    "en": {"title": "FAQ", "guide": "Start interactive guide", "close": "Got it"},
    "ru": {"title": "Справка", "guide": "Пройти обучение", "close": "Понятно"},
    "es": {"title": "Ayuda", "guide": "Iniciar guía", "close": "Entendido"},
    "de": {"title": "Hilfe", "guide": "Tour starten", "close": "Verstanden"},
    "fr": {"title": "Aide", "guide": "Lancer le guide", "close": "Compris"},
    "zh": {"title": "帮助", "guide": "开始引导", "close": "知道了"},
}


def help_action_text(lang, key):
    text = HELP_ACTION_TEXT.get(lang, HELP_ACTION_TEXT["en"])
    return text.get(key, HELP_ACTION_TEXT["en"].get(key, key))


def help_text(lang):
    sections = (
        HELP_CONTENT.get(lang, HELP_CONTENT["en"])
        + DOCUMENT_HELP_CONTENT.get(lang, DOCUMENT_HELP_CONTENT["en"])
        + HELP_EXTRA_CONTENT.get(lang, HELP_EXTRA_CONTENT["en"])
    )
    intro = HELP_INTRO.get(lang, HELP_INTRO["en"])
    blocks = [_HELP_STYLE, f'<div class="hero"><div class="hero-title">Click&apos;n&apos;Translate</div><div class="hero-subtitle">{intro}</div></div>']
    for title, items in sections:
        blocks.append(f'<div class="section"><div class="section-title">{title}</div>')
        for item in items:
            blocks.append(f'<div class="item">{item}</div>')
        blocks.append("</div>")
    return "\n".join(blocks)

THEMES = {
    "Темная": {
        "background": "#121212",
        "text_color": "#ffffff",
        "button_background": "#1e1e1e",
        "button_border": "#550000",
        "button_hover": "#333333",
        "item_hover_background": "#333333",
        "item_hover_color": "#ffffff",
        "item_selected_background": "#444444",
        "item_selected_color": "#ffffff",
    },
    "Светлая": {
        "background": "#ffffff",
        "text_color": "#000000",
        "button_background": "#f0f0f0",
        "button_border": "#cccccc",
        "button_hover": "#e0e0e0",
        "item_hover_background": "#e0e0e0",
        "item_hover_color": "#000000",
        "item_selected_background": "#c0c0c0",
        "item_selected_color": "#000000",
    }
}

def resource_path(relative_path):
    """ Получить абсолютный путь к ресурсу, работает для dev и для PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class WelcomeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self._drag_position = None
        self._animations = []
        self.start_guide_requested = False
        self.lang = normalize_interface_language(
            parent.current_interface_language if hasattr(parent, 'current_interface_language') else 'ru'
        )
        self.setWindowTitle(welcome_text(self.lang)["window"])
        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        self.setFixedSize(560, 390)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.init_ui()

    def init_ui(self):
        previous_checked = bool(getattr(getattr(self, "checkbox", None), "isChecked", lambda: False)())
        self._stop_animations()
        self._clear_layout()
        text = welcome_text(self.lang)
        self.setWindowTitle(text["window"])
        self.setStyleSheet("""
            QDialog {
                background: transparent;
            }
            QFrame#welcomeCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #111827, stop:0.48 #15101f, stop:1 #241735);
                border: 1px solid rgba(197, 179, 233, 120);
                border-radius: 20px;
            }
            QLabel {
                color: #f7f2ff;
                background: transparent;
            }
            QLabel#welcomeLogo {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #c5b3e9, stop:1 #7a5fa1);
                color: #111827;
                border-radius: 15px;
                font-size: 17px;
                font-weight: 900;
            }
            QLabel#welcomeEyebrow {
                color: #c5b3e9;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            QLabel#welcomeTitle {
                color: #ffffff;
                font-size: 27px;
                font-weight: 900;
            }
            QLabel#welcomeBody {
                color: #d8d2e8;
                font-size: 14px;
                line-height: 1.45;
            }
            QLabel#welcomeVersion {
                color: #a994d2;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#welcomeChip {
                color: #efe8ff;
                background: rgba(197, 179, 233, 30);
                border: 1px solid rgba(197, 179, 233, 80);
                border-radius: 12px;
                padding: 7px 10px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#welcomeLang,
            QPushButton#welcomeClose {
                background: rgba(255, 255, 255, 16);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 42);
                border-radius: 12px;
            }
            QPushButton#welcomeLang:hover,
            QPushButton#welcomeClose:hover {
                background: rgba(197, 179, 233, 60);
                border: 1px solid rgba(223, 212, 255, 150);
            }
            QPushButton#welcomeTelegram {
                background: rgba(42, 171, 238, 26);
                color: #d9f2ff;
                border: 1px solid rgba(42, 171, 238, 110);
                border-radius: 13px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton#welcomeTelegram:hover {
                background: rgba(42, 171, 238, 48);
            }
            QPushButton#welcomeStart {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #c5b3e9, stop:1 #8f6fd1);
                color: #111827;
                border: none;
                border-radius: 13px;
                padding: 10px 22px;
                font-size: 15px;
                font-weight: 900;
            }
            QPushButton#welcomeStart:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #dfd4ff, stop:1 #a681eb);
            }
            QPushButton#welcomeSkip {
                background: rgba(255, 255, 255, 12);
                color: #d8d2e8;
                border: 1px solid rgba(197, 179, 233, 72);
                border-radius: 13px;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: 800;
            }
            QPushButton#welcomeSkip:hover {
                background: rgba(197, 179, 233, 34);
                color: #ffffff;
            }
            QCheckBox {
                color: #bdb4d1;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border-radius: 5px;
                border: 1px solid #7a5fa1;
                background: rgba(255,255,255,18);
            }
            QCheckBox::indicator:checked {
                background: #c5b3e9;
                border: 1px solid #c5b3e9;
            }
        """)

        if self.layout() is None:
            self.main_layout = QVBoxLayout(self)
        else:
            self.main_layout = self.layout()
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        self.main_layout.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("welcomeCard")
        self.main_layout.addWidget(card)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 22)
        card_layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        logo = QLabel("CT")
        logo.setObjectName("welcomeLogo")
        logo.setFixedSize(42, 42)
        logo.setAlignment(Qt.AlignCenter)
        top_row.addWidget(logo)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        app_name = QLabel("Click'n'Translate")
        app_name.setStyleSheet("font-size: 17px; font-weight: 900; color: #ffffff;")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("welcomeVersion")
        title_stack.addWidget(app_name)
        title_stack.addWidget(version)
        top_row.addLayout(title_stack)
        top_row.addStretch()

        self.flag_button = QPushButton()
        self.flag_button.setObjectName("welcomeLang")
        self.flag_button.setIcon(QIcon(resource_path(get_interface_language_option(self.lang)["icon"])))
        self.flag_button.setIconSize(QSize(24, 24))
        self.flag_button.setFixedSize(46, 38)
        self.flag_button.clicked.connect(self.show_language_menu)
        top_row.addWidget(self.flag_button)

        close_x = QPushButton("×")
        close_x.setObjectName("welcomeClose")
        close_x.setFixedSize(38, 38)
        close_x.setStyleSheet("font-size: 22px; font-weight: 700;")
        close_x.clicked.connect(self.skip_guide)
        top_row.addWidget(close_x)
        card_layout.addLayout(top_row)

        hero = QVBoxLayout()
        hero.setSpacing(8)
        eyebrow = QLabel(text["eyebrow"])
        eyebrow.setObjectName("welcomeEyebrow")
        hero.addWidget(eyebrow)

        title = QLabel(text["title"])
        title.setObjectName("welcomeTitle")
        title.setWordWrap(True)
        hero.addWidget(title)

        body = QLabel(text["body"])
        body.setObjectName("welcomeBody")
        body.setWordWrap(True)
        hero.addWidget(body)
        card_layout.addLayout(hero)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        for key in ("feature_ocr", "feature_translate", "feature_updates"):
            chip = QLabel(text[key])
            chip.setObjectName("welcomeChip")
            chip.setAlignment(Qt.AlignCenter)
            chips.addWidget(chip)
        card_layout.addLayout(chips)
        card_layout.addStretch()

        self.checkbox = QCheckBox(text["checkbox"])
        self.checkbox.setChecked(previous_checked)
        card_layout.addWidget(self.checkbox)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.telegram_btn = QPushButton(text["telegram"])
        self.telegram_btn.setObjectName("welcomeTelegram")
        self.telegram_btn.clicked.connect(self.open_telegram)
        actions.addWidget(self.telegram_btn)
        actions.addStretch()

        self.skip_btn = QPushButton(text["skip"])
        self.skip_btn.setObjectName("welcomeSkip")
        self.skip_btn.clicked.connect(self.skip_guide)
        actions.addWidget(self.skip_btn)

        self.guide_btn = QPushButton(text["guide"])
        self.guide_btn.setObjectName("welcomeStart")
        self.guide_btn.clicked.connect(self.start_guide)
        actions.addWidget(self.guide_btn)
        card_layout.addLayout(actions)

        QTimer.singleShot(120, self._pulse_flag_button)

    def _pulse_flag_button(self):
        if not getattr(self, "flag_button", None):
            return
        glow = QGraphicsDropShadowEffect(self.flag_button)
        glow.setOffset(0, 0)
        glow.setColor(QColor(197, 179, 233, 210))
        glow.setBlurRadius(16)
        self.flag_button.setGraphicsEffect(glow)

        animation = QtCore.QPropertyAnimation(glow, b"blurRadius", self)
        animation.setStartValue(10)
        animation.setEndValue(30)
        animation.setDuration(1050)
        animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        animation.setLoopCount(-1)
        animation.start()
        self._animations.append(animation)

    def _stop_animations(self):
        for animation in getattr(self, "_animations", []):
            try:
                animation.stop()
            except Exception:
                pass
        self._animations = []

    def _clear_layout(self):
        layout = self.layout()
        if layout is None:
            return
        while layout.count():
            self._delete_layout_item(layout.takeAt(0))

    def _delete_layout_item(self, item):
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        child_layout = item.layout()
        if child_layout is not None:
            while child_layout.count():
                self._delete_layout_item(child_layout.takeAt(0))

    def open_telegram(self):
        webbrowser.open("https://t.me/jabrail_digital")

    def start_guide(self):
        self.start_guide_requested = True
        self.accept()

    def skip_guide(self):
        self.start_guide_requested = False
        self.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def toggle_language(self):
        codes = [option["code"] for option in INTERFACE_LANGUAGE_OPTIONS]
        index = codes.index(self.lang) if self.lang in codes else 0
        self.set_language(codes[(index + 1) % len(codes)])

    def show_language_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0f131c;
                color: #ffffff;
                border: 1px solid #6f5a99;
                border-radius: 10px;
                padding: 6px;
            }
            QMenu::item {
                padding: 8px 22px 8px 10px;
                border-radius: 8px;
                font-weight: 700;
            }
            QMenu::item:selected {
                background-color: rgba(197, 179, 233, 64);
            }
            QMenu::indicator {
                width: 0px;
            }
        """)
        for option in INTERFACE_LANGUAGE_OPTIONS:
            selected = option["code"] == self.lang
            action = menu.addAction(QIcon(resource_path(option["icon"])), ("• " if selected else "  ") + option["name"])
            action.triggered.connect(lambda _checked=False, code=option["code"]: self.set_language(code))
        menu.exec_(self.flag_button.mapToGlobal(self.flag_button.rect().bottomLeft()))

    def set_language(self, language_code):
        self.lang = normalize_interface_language(language_code)
        if self.parent is not None:
            self.parent.current_interface_language = self.lang
            if hasattr(self.parent, "config"):
                self.parent.config["interface_language"] = self.lang
            if hasattr(self.parent, "save_config"):
                self.parent.save_config()
        self.init_ui()

    def accept(self):
        self._stop_animations()
        super().accept()

    def closeEvent(self, event):
        self._stop_animations()
        super().closeEvent(event)

class DocumentTranslationDialog(QDialog):
    _document_loaded_signal = QtCore.pyqtSignal(object)
    _document_error_signal = QtCore.pyqtSignal(str)
    _document_progress_signal = QtCore.pyqtSignal(int, int, str)
    _document_done_signal = QtCore.pyqtSignal(str, object)

    def __init__(self, parent_app, initial_path=None):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.lang = getattr(parent_app, "current_interface_language", "en")
        self.theme_name = getattr(parent_app, "current_theme", DEFAULT_CONFIG["theme"])
        self.current_document = None
        self.session_payload = None
        self.translated_text = ""
        self.translation_results = []
        self.translation_error_message_visible = False
        self.translation_running = False

        self._document_loaded_signal.connect(self._on_document_loaded)
        self._document_error_signal.connect(self._on_document_error)
        self._document_progress_signal.connect(self._on_translation_progress)
        self._document_done_signal.connect(self._on_translation_done)

        self.setWindowTitle(doc_text(self.lang, "title"))
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))
        self.setMinimumSize(980, 680)
        self.resize(1080, 700)
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._build_ui()
        self._apply_dialog_theme()
        self._apply_native_frame_theme()
        self._set_status(doc_text(self.lang, "no_file"))
        self._set_busy(False)
        if initial_path:
            QTimer.singleShot(0, lambda: self.load_file(initial_path))

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_native_frame_theme()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("docTopBar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 12)
        header_layout.setSpacing(12)

        header_top = QHBoxLayout()
        header_top.setSpacing(12)
        self.doc_icon_label = QLabel()
        self.doc_icon_label.setObjectName("docHeaderIcon")
        self.doc_icon_label.setFixedSize(38, 38)
        self.doc_icon_label.setAlignment(Qt.AlignCenter)
        header_top.addWidget(self.doc_icon_label)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(2)
        self.header_title = QLabel(doc_text(self.lang, "title"))
        self.header_title.setObjectName("docTitle")
        self.header_subtitle = QLabel(doc_text(self.lang, "drop_hint"))
        self.header_subtitle.setObjectName("docSubtitle")
        title_stack.addWidget(self.header_title)
        title_stack.addWidget(self.header_subtitle)
        self.metadata_label = QLabel("")
        self.metadata_label.setObjectName("docMetadata")
        self.metadata_label.setWordWrap(False)
        self.metadata_label.setTextFormat(Qt.PlainText)
        title_stack.addWidget(self.metadata_label)
        header_top.addLayout(title_stack, 1)

        self.status_pill = QLabel(doc_text(self.lang, "no_file"))
        self.status_pill.setObjectName("docStatusPill")
        self.status_pill.setAlignment(Qt.AlignCenter)
        self.status_pill.setMinimumWidth(128)
        header_top.addWidget(self.status_pill)
        header_layout.addLayout(header_top)

        control_row = QHBoxLayout()
        control_row.setSpacing(10)
        self.source_field_label = QLabel(doc_text(self.lang, "source") + ":")
        self.source_field_label.setObjectName("docFieldLabel")
        control_row.addWidget(self.source_field_label)
        self.source_combo = QComboBox()
        self.source_combo.addItem(doc_text(self.lang, "auto_detect"))
        self.source_combo.addItems(LANGUAGES[self.lang])
        self.source_combo.setMinimumWidth(150)
        control_row.addWidget(self.source_combo)

        self.language_arrow = QLabel("→")
        self.language_arrow.setObjectName("docArrow")
        self.language_arrow.setAlignment(Qt.AlignCenter)
        control_row.addWidget(self.language_arrow)

        self.target_field_label = QLabel(doc_text(self.lang, "target") + ":")
        self.target_field_label.setObjectName("docFieldLabel")
        control_row.addWidget(self.target_field_label)
        self.target_combo = QComboBox()
        self.target_combo.addItems(LANGUAGES[self.lang])
        target_widget = getattr(self.parent_app, "target_lang", None)
        if target_widget is not None:
            try:
                target_text = target_widget.currentText()
                target_index = self.target_combo.findText(target_text)
                if target_index >= 0:
                    self.target_combo.setCurrentIndex(target_index)
            except RuntimeError:
                pass
        self.target_combo.currentIndexChanged.connect(self._update_metadata)
        self.target_combo.setMinimumWidth(150)
        control_row.addWidget(self.target_combo)

        self.provider_field_label = QLabel(doc_text(self.lang, "provider") + ":")
        self.provider_field_label.setObjectName("docFieldLabel")
        control_row.addWidget(self.provider_field_label)
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(170)
        self._populate_provider_combo()
        self.provider_combo.currentIndexChanged.connect(self._update_metadata)
        control_row.addWidget(self.provider_combo)
        control_row.addStretch(1)
        header_layout.addLayout(control_row)
        layout.addWidget(header)

        actions_frame = QFrame()
        actions_frame.setObjectName("docToolBar")
        actions_frame.setAttribute(Qt.WA_StyledBackground, True)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(18, 10, 18, 10)
        toolbar.setSpacing(8)
        self.attach_button = QPushButton(doc_text(self.lang, "attach_file"))
        self.attach_button.setObjectName("docButton")
        self.attach_button.clicked.connect(self.attach_file)
        toolbar.addWidget(self.attach_button)

        self.open_button = QPushButton(doc_text(self.lang, "open_session"))
        self.open_button.setObjectName("docButton")
        self.open_button.clicked.connect(self.open_session)
        toolbar.addWidget(self.open_button)

        self.remove_button = QPushButton(doc_text(self.lang, "remove_file"))
        self.remove_button.setObjectName("docDangerButton")
        self.remove_button.clicked.connect(self.remove_file)
        toolbar.addWidget(self.remove_button)

        toolbar.addStretch(1)

        self.translate_selected_button = QPushButton(doc_text(self.lang, "translate_selected"))
        self.translate_selected_button.setObjectName("docButton")
        self.translate_selected_button.clicked.connect(self.translate_selected_text)
        toolbar.addWidget(self.translate_selected_button)

        self.translate_file_button = QPushButton(doc_text(self.lang, "translate_file"))
        self.translate_file_button.setObjectName("docPrimaryButton")
        self.translate_file_button.clicked.connect(self.translate_file)
        toolbar.addWidget(self.translate_file_button)

        self.save_button = QPushButton(doc_text(self.lang, "save_translation"))
        self.save_button.setObjectName("docButton")
        self.save_button.clicked.connect(self.save_translation)
        toolbar.addWidget(self.save_button)
        actions_frame.setLayout(toolbar)
        layout.addWidget(actions_frame)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("docProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumHeight(5)
        layout.addWidget(self.progress_bar)

        content_frame = QFrame()
        content_frame.setObjectName("docContent")
        content_frame.setAttribute(Qt.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(0)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setObjectName("docSplitter")
        splitter.addWidget(self._reader_column(doc_text(self.lang, "original"), True))
        splitter.addWidget(self._reader_column(doc_text(self.lang, "translated"), False))
        splitter.setSizes([490, 490])
        content_layout.addWidget(splitter, 1)
        layout.addWidget(content_frame, 1)

    def _reader_column(self, title, original):
        frame = QFrame()
        frame.setObjectName("docPane")
        frame.setAttribute(Qt.WA_StyledBackground, True)
        column = QVBoxLayout(frame)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        header = QFrame()
        header.setObjectName("docPaneHeader")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 10, 14, 8)
        header_layout.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("docPaneTitle")
        header_layout.addWidget(label)
        header_layout.addStretch(1)
        column.addWidget(header)

        editor = QTextEdit()
        editor.setObjectName("docEditor")
        editor.setReadOnly(not original)
        editor.setLineWrapMode(QTextEdit.WidgetWidth)
        editor.setAcceptDrops(False)
        editor.setFrameShape(QFrame.NoFrame)
        if original:
            self.original_label = label
            self.original_view = editor
            editor.setPlaceholderText(doc_text(self.lang, "drop_hint"))
            editor.textChanged.connect(self._on_original_text_changed)
        else:
            self.translated_label = label
            self.translated_view = editor
        column.addWidget(editor, 1)
        return frame

    def _apply_dialog_theme(self):
        is_dark = self.theme_name == DEFAULT_CONFIG["theme"]
        bg = "#0E1116" if is_dark else "#F3F5F8"
        top = "#151A22" if is_dark else "#FFFFFF"
        toolbar = "#10151D" if is_dark else "#F8FAFC"
        pane = "#111821" if is_dark else "#FFFFFF"
        editor = "#0B0F15" if is_dark else "#FBFCFE"
        control = "#1D2430" if is_dark else "#EEF2F7"
        control_hover = "#26303F" if is_dark else "#E3E8F0"
        border = "#2D3746" if is_dark else "#D8DEE8"
        soft_border = "#222B38" if is_dark else "#E8ECF2"
        fg = "#F3F6FA" if is_dark else "#141922"
        muted = "#9CA8B8" if is_dark else "#697587"
        faint = "#6F7B8B" if is_dark else "#8792A2"
        accent = "#8F6FD1" if is_dark else "#6D55BE"
        accent_hover = "#A98BE7" if is_dark else "#5D47A6"
        accent_text = "#0E1116" if is_dark else "#FFFFFF"
        danger = "#EB6D72" if is_dark else "#B84D57"
        if hasattr(self, "doc_icon_label"):
            self.doc_icon_label.setPixmap(document_translation_icon(self.theme_name).pixmap(30, 30))
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
                color: {fg};
            }}
            QLabel {{
                color: {fg};
                font-size: 13px;
            }}
            QFrame#docTopBar {{
                background-color: {top};
                border-bottom: 1px solid {soft_border};
            }}
            QFrame#docToolBar {{
                background-color: {toolbar};
                border-bottom: 1px solid {soft_border};
            }}
            QFrame#docContent {{
                background-color: {bg};
            }}
            QFrame#docPane {{
                background-color: {pane};
                border: 1px solid {border};
                border-radius: 7px;
            }}
            QFrame#docPaneHeader {{
                background-color: transparent;
                border-bottom: 1px solid {soft_border};
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
            }}
            QLabel#docHeaderIcon {{
                background-color: {control};
                border: 1px solid {border};
                border-radius: 10px;
            }}
            QLabel#docTitle {{
                color: {fg};
                font-size: 18px;
                font-weight: 900;
            }}
            QLabel#docSubtitle,
            QLabel#docMetadata,
            QLabel#docProvider {{
                color: {muted};
                font-size: 12px;
                font-weight: 600;
            }}
            QLabel#docMetadata {{
                color: {faint};
            }}
            QLabel#docStatusPill {{
                color: {fg};
                background-color: {control};
                border: 1px solid {border};
                border-radius: 11px;
                padding: 5px 10px;
                font-size: 12px;
                font-weight: 800;
            }}
            QLabel#docArrow {{
                color: {muted};
                font-size: 16px;
                font-weight: 900;
            }}
            QLabel#docFieldLabel {{
                color: {muted};
                font-size: 12px;
                font-weight: 800;
            }}
            QLabel#docPaneTitle {{
                color: {fg};
                font-size: 13px;
                font-weight: 900;
            }}
            QPushButton {{
                min-height: 28px;
            }}
            QPushButton#docButton {{
                background-color: {control};
                color: {fg};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 6px 11px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#docButton:hover {{
                background-color: {control_hover};
                border-color: {accent};
            }}
            QPushButton#docPrimaryButton {{
                background-color: {accent};
                color: {accent_text};
                border: 1px solid {accent};
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 900;
            }}
            QPushButton#docPrimaryButton:hover {{
                background-color: {accent_hover};
                border-color: {accent_hover};
            }}
            QPushButton#docDangerButton {{
                background-color: transparent;
                color: {danger};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 6px 11px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton#docDangerButton:hover {{
                background-color: {control_hover};
                border-color: {danger};
            }}
            QPushButton:disabled {{
                color: #777777;
                background-color: {control};
                border-color: {soft_border};
            }}
            QComboBox {{
                background-color: {control};
                color: {fg};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {accent};
            }}
            QComboBox QAbstractItemView {{
                background-color: {pane};
                color: {fg};
                border: 1px solid {border};
                selection-background-color: {control_hover};
            }}
            QTextEdit#docEditor {{
                background-color: {editor};
                color: {fg};
                border: none;
                border-bottom-left-radius: 7px;
                border-bottom-right-radius: 7px;
                padding: 14px;
                font-size: 14px;
                line-height: 1.4;
                selection-background-color: {accent};
                selection-color: {accent_text};
            }}
            QTextEdit#docEditor:focus {{
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 5px 2px 5px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                min-height: 34px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {accent};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
                background: none;
            }}
            QProgressBar#docProgress {{
                background-color: {control};
                border: none;
                border-radius: 0;
                max-height: 5px;
                text-align: center;
            }}
            QProgressBar#docProgress::chunk {{
                background-color: {accent};
                border-radius: 0;
            }}
            QSplitter#docSplitter::handle {{
                background-color: transparent;
                width: 10px;
            }}
        """)

    def _apply_native_frame_theme(self):
        apply_windows_dark_frame(self, self.theme_name == DEFAULT_CONFIG["theme"])

    def refresh_theme(self, theme_name):
        self.theme_name = theme_name
        self._apply_dialog_theme()
        self._apply_native_frame_theme()

    def refresh_language(self, language_code):
        old_lang = self.lang
        source_code = self._source_code()
        target_code = language_code_from_name(self.target_combo.currentText(), old_lang)
        self.lang = normalize_interface_language(language_code)

        self.setWindowTitle(doc_text(self.lang, "title"))
        self.header_title.setText(doc_text(self.lang, "title"))
        self.header_subtitle.setText(doc_text(self.lang, "drop_hint"))
        self.attach_button.setText(doc_text(self.lang, "attach_file"))
        self.remove_button.setText(doc_text(self.lang, "remove_file"))
        self.translate_file_button.setText(doc_text(self.lang, "translate_file"))
        self.translate_selected_button.setText(doc_text(self.lang, "translate_selected"))
        self.save_button.setText(doc_text(self.lang, "save_translation"))
        self.open_button.setText(doc_text(self.lang, "open_session"))
        self.source_field_label.setText(doc_text(self.lang, "source") + ":")
        self.target_field_label.setText(doc_text(self.lang, "target") + ":")
        self.original_label.setText(doc_text(self.lang, "original"))
        self.translated_label.setText(doc_text(self.lang, "translated"))
        self.original_view.setPlaceholderText(doc_text(self.lang, "drop_hint"))

        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItem(doc_text(self.lang, "auto_detect"))
        self.source_combo.addItems(LANGUAGES[self.lang])
        self.source_combo.setCurrentIndex(0)
        if source_code != "auto":
            self._set_combo_to_language_code(self.source_combo, source_code)
        self.source_combo.blockSignals(False)

        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItems(LANGUAGES[self.lang])
        self._set_combo_to_language_code(self.target_combo, target_code)
        self.target_combo.blockSignals(False)

        self.provider_field_label.setText(doc_text(self.lang, "provider") + ":")
        provider_engine = self._provider_engine()
        self._populate_provider_combo(provider_engine)
        if self.translation_running:
            self.current_status = doc_text(self.lang, "translating")
        elif self.current_document:
            self.current_status = doc_text(self.lang, "loaded")
        elif self.session_payload:
            self.current_status = doc_text(self.lang, "session_loaded")
        else:
            self.current_status = doc_text(self.lang, "no_file")
        self.status_pill.setText(self.current_status)
        self._update_metadata()

    def _set_combo_to_language_code(self, combo, language_code):
        for index in range(combo.count()):
            if language_code_from_name(combo.itemText(index), self.lang) == language_code:
                combo.setCurrentIndex(index)
                return

    def _on_original_text_changed(self):
        if self.current_document or self.session_payload or self.translation_running:
            return
        if self.original_view.toPlainText().strip():
            self._set_status(doc_text(self.lang, "loaded"))
        else:
            self.translated_text = ""
            self.translation_results = []
            self.translation_error_message_visible = False
            self.translated_view.clear()
            self.progress_bar.setValue(0)
            self._set_status(doc_text(self.lang, "no_file"))
        self._set_busy(False)

    def attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            doc_text(self.lang, "attach_file"),
            "",
            "Documents (*.txt *.md *.docx *.pdf *.html *.htm *.rtf);;All files (*.*)",
        )
        if path:
            self.load_file(path)

    def load_file(self, path):
        if self.translation_running:
            return
        self.current_document = None
        self.session_payload = None
        self.translated_text = ""
        self.translation_results = []
        self.translation_error_message_visible = False
        self.original_view.blockSignals(True)
        self.original_view.clear()
        self.original_view.blockSignals(False)
        self.translated_view.clear()
        self.progress_bar.setRange(0, 0)
        self._set_status(doc_text(self.lang, "loading"))
        self._set_busy(True, loading=True)

        def worker():
            try:
                document = parse_document(path)
                self._document_loaded_signal.emit(document)
            except DocumentParseError as exc:
                self._document_error_signal.emit(str(exc))
            except Exception as exc:
                self._document_error_signal.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_document_loaded(self, document):
        self.current_document = document
        self.session_payload = None
        self.original_view.blockSignals(True)
        self.original_view.setPlainText(document.text)
        self.original_view.blockSignals(False)
        self.translated_view.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_busy(False)
        self._set_status(doc_text(self.lang, "loaded"))

    def _on_document_error(self, message):
        self.translation_running = False
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_busy(False)
        self._set_status(str(message))
        QMessageBox.warning(self, doc_text(self.lang, "error"), str(message))

    def remove_file(self):
        if self.translation_running:
            return
        self.current_document = None
        self.session_payload = None
        self.translated_text = ""
        self.translation_results = []
        self.translation_error_message_visible = False
        self.original_view.blockSignals(True)
        self.original_view.clear()
        self.original_view.blockSignals(False)
        self.translated_view.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_status(doc_text(self.lang, "no_file"))
        self._set_busy(False)

    def translate_file(self):
        if not self.current_document and not self.original_view.toPlainText().strip():
            QMessageBox.information(self, doc_text(self.lang, "title"), doc_text(self.lang, "no_file"))
            return
        self._start_translation(self.original_view.toPlainText())

    def translate_selected_text(self):
        selected = self.original_view.textCursor().selectedText().replace("\u2029", "\n").strip()
        if not selected:
            QMessageBox.information(self, doc_text(self.lang, "title"), doc_text(self.lang, "no_selection"))
            return
        self._start_translation(selected)

    def _start_translation(self, text):
        text = str(text or "").strip()
        if not text or self.translation_running:
            return
        self.translation_running = True
        self.translated_text = ""
        self.translation_results = []
        self.translation_error_message_visible = False
        self.translated_view.clear()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._set_busy(True)
        self._set_status(doc_text(self.lang, "translating"))

        source_code = self._source_code()
        target_code = language_code_from_name(self.target_combo.currentText(), self.lang)

        def progress(done, total, message):
            self._document_progress_signal.emit(int(done), int(total), str(message))

        def worker():
            try:
                translated, results = translate_document_text(
                    text,
                    source_code,
                    target_code,
                    provider_engine=self._provider_engine(),
                    progress_callback=progress,
                )
                self._document_done_signal.emit(translated, results)
            except Exception as exc:
                self._document_error_signal.emit(str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_translation_progress(self, done, total, message):
        if total:
            self.progress_bar.setValue(max(0, min(100, int(done * 100 / total))))
            self._set_status(f"{doc_text(self.lang, 'translating')}: {done}/{total}")
        else:
            self.progress_bar.setValue(0)
            self._set_status(message)

    def _on_translation_done(self, translated, results):
        self.translation_running = False
        self.translation_results = list(results or [])
        friendly_failure = self._friendly_provider_failure_text(self.translation_results)
        self.translation_error_message_visible = bool(friendly_failure)
        self.translated_text = friendly_failure or (translated or "")
        self.translated_view.setPlainText(self.translated_text)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._set_busy(False)
        failed = sum(1 for result in self.translation_results if getattr(result, "error", ""))
        if friendly_failure:
            self._set_status(doc_text(self.lang, "provider_unavailable_title"))
        elif failed:
            self._set_status(f"{doc_text(self.lang, 'translate_failed')}: {failed}")
        else:
            self._set_status(doc_text(self.lang, "done"))

    def _friendly_provider_failure_text(self, results):
        results = list(results or [])
        if not results:
            return ""
        failed_results = [result for result in results if getattr(result, "error", "")]
        if not failed_results or len(failed_results) != len(results):
            return ""

        engine = self._provider_engine()
        provider_name = self._provider_name()
        first_error = str(getattr(failed_results[0], "error", "") or "").strip()
        error_lower = first_error.lower()

        if engine == "argos" or "argos offline translation package" in error_lower:
            advice_key = "provider_unavailable_argos"
        elif engine == "hymt" or "hy-mt" in error_lower or "hymt" in error_lower:
            advice_key = "provider_unavailable_hymt"
        elif engine in {"google", "mymemory", "lingva", "libretranslate"}:
            advice_key = "provider_unavailable_online"
        else:
            advice_key = "provider_unavailable_generic"

        return (
            f"{doc_text(self.lang, 'provider_unavailable_title')}: {provider_name}\n\n"
            f"{doc_text(self.lang, advice_key)}\n\n"
            f"{doc_text(self.lang, 'technical_error')}:\n{first_error}"
        ).strip()

    def save_translation(self):
        if self.translation_error_message_visible:
            QMessageBox.information(self, doc_text(self.lang, "title"), doc_text(self.lang, "provider_unavailable_title"))
            return
        if not self.translated_text.strip():
            QMessageBox.information(self, doc_text(self.lang, "title"), doc_text(self.lang, "no_translation"))
            return
        paths = default_output_paths(self._data_dir(), self._source_file_name())
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            doc_text(self.lang, "save_translation"),
            paths["txt"],
            "Text file (*.txt);;Markdown file (*.md);;Session file (*.json)",
        )
        if not path:
            return

        selected_filter = selected_filter or ""
        root, ext = os.path.splitext(path)
        if "Markdown" in selected_filter and not ext:
            path = root + ".md"
        elif "Session" in selected_filter and not ext:
            path = root + ".json"
        elif not ext:
            path = root + ".txt"

        if path.lower().endswith(".json"):
            save_session(path, self._session_payload())
        else:
            save_text(path, self.translated_text)
            save_session(paths["session"], self._session_payload())
        self._set_status(f"{doc_text(self.lang, 'saved')}: {path}")

    def open_session(self):
        root = translations_dir(self._data_dir())
        path, _ = QFileDialog.getOpenFileName(
            self,
            doc_text(self.lang, "open_session"),
            root,
            "Translation sessions (*.json);;All files (*.*)",
        )
        if not path:
            return
        try:
            payload = load_session(path)
        except Exception as exc:
            QMessageBox.warning(self, doc_text(self.lang, "error"), str(exc))
            return
        self.current_document = None
        self.session_payload = payload
        self.translated_text = payload.get("translated_text", "")
        self.translation_results = []
        self.translation_error_message_visible = False
        self.original_view.blockSignals(True)
        self.original_view.setPlainText(payload.get("original_text", ""))
        self.original_view.blockSignals(False)
        self.translated_view.setPlainText(self.translated_text)
        if payload.get("provider_engine"):
            self._populate_provider_combo(payload.get("provider_engine"))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if self.translated_text else 0)
        self._set_status(doc_text(self.lang, "session_loaded"))
        self._set_busy(False)

    def _source_code(self):
        if self.source_combo.currentIndex() == 0:
            return "auto"
        return language_code_from_name(self.source_combo.currentText(), self.lang)

    def _populate_provider_combo(self, selected_engine=None):
        selected_engine = str(selected_engine or get_cached_config().get("translator_engine", "Google")).lower()
        if selected_engine == "hy-mt":
            selected_engine = "hymt"
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        selected_index = 0
        for index, (engine, _name, _kind) in enumerate(TRANSLATION_PROVIDER_OPTIONS):
            self.provider_combo.addItem(provider_display_name(engine, self.lang, include_kind=True), engine)
            if engine == selected_engine:
                selected_index = index
        self.provider_combo.setCurrentIndex(selected_index)
        self.provider_combo.blockSignals(False)

    def _provider_engine(self):
        if hasattr(self, "provider_combo"):
            engine = self.provider_combo.currentData()
            if engine:
                return str(engine).lower()
        return str(get_cached_config().get("translator_engine", "Google")).lower()

    def _provider_name(self):
        return provider_display_name(self._provider_engine(), self.lang)

    def _data_dir(self):
        return os.path.dirname(get_data_file("config.json"))

    def _source_file_name(self):
        if self.current_document:
            return self.current_document.file_name
        if self.session_payload:
            return self.session_payload.get("source_file_name") or "translation"
        return "translation"

    def _session_payload(self):
        source_code = self._source_code()
        target_code = language_code_from_name(self.target_combo.currentText(), self.lang)
        document = self.current_document
        return {
            "source_file_name": self._source_file_name(),
            "source_path": document.path if document else self.session_payload.get("source_path", "") if self.session_payload else "",
            "source_size": document.size_bytes if document else self.session_payload.get("source_size", 0) if self.session_payload else 0,
            "detected_language": document.detected_language if document else self.session_payload.get("detected_language", "") if self.session_payload else "",
            "source_language": source_code,
            "target_language": target_code,
            "provider": self._provider_name(),
            "provider_engine": self._provider_engine(),
            "original_text": self.original_view.toPlainText(),
            "translated_text": self.translated_text,
            "chunks": [
                {
                    "index": result.index,
                    "source_text": result.source_text,
                    "translated_text": result.translated_text,
                    "error": result.error,
                }
                for result in self.translation_results
            ],
        }

    def _set_status(self, status):
        self.current_status = str(status)
        if hasattr(self, "status_pill"):
            self.status_pill.setText(self.current_status)
        self._update_metadata()

    def _update_metadata(self):
        target = self.target_combo.currentText() if hasattr(self, "target_combo") else ""
        if self.current_document:
            parts = [
                f"{doc_text(self.lang, 'file')}: {self.current_document.file_name}",
                f"{doc_text(self.lang, 'size')}: {format_file_size(self.current_document.size_bytes)}",
                f"{doc_text(self.lang, 'detected')}: {self.current_document.detected_language.upper()}",
                f"{doc_text(self.lang, 'target')}: {target}",
                f"{doc_text(self.lang, 'provider')}: {self._provider_name()}",
            ]
        elif self.session_payload:
            size = self.session_payload.get("source_size", 0)
            parts = [
                f"{doc_text(self.lang, 'file')}: {self._source_file_name()}",
                f"{doc_text(self.lang, 'size')}: {format_file_size(size)}",
                f"{doc_text(self.lang, 'target')}: {target}",
                f"{doc_text(self.lang, 'provider')}: {self.session_payload.get('provider', self._provider_name())}",
            ]
        else:
            parts = [
                doc_text(self.lang, "loaded") if self.original_view.toPlainText().strip() else doc_text(self.lang, "drop_hint"),
                f"{doc_text(self.lang, 'provider')}: {self._provider_name()}",
            ]
        self.metadata_label.setText("  •  ".join(parts))

    def _set_busy(self, busy, loading=False):
        has_translation = bool(str(self.translated_text or "").strip())
        self.attach_button.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        self.remove_button.setEnabled(not busy)
        self.translate_file_button.setEnabled(not busy)
        self.translate_selected_button.setEnabled(not busy)
        self.save_button.setEnabled(not busy and has_translation and not self.translation_error_message_visible)
        self.source_combo.setEnabled(not busy)
        self.target_combo.setEnabled(not busy)
        self.provider_combo.setEnabled(not busy)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and event.mimeData().urls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.load_file(path)
                event.acceptProposedAction()
                return
        super().dropEvent(event)


class DarkThemeApp(QMainWindow):
    # Signal to show translation dialog from background thread
    _show_selection_signal = QtCore.pyqtSignal(str, bool, str, str)

    def __init__(self):
        super().__init__()
        self._show_selection_signal.connect(self._show_selection_translation)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowTitle(APP_WINDOW_TITLE)
        self.setFixedSize(700, 400)
        self._is_dragging = False
        self.setAcceptDrops(True)
        self.document_dialog = None
        # Важно для single-instance в режиме "start minimized":
        # создаем native HWND заранее, чтобы окно могло получить Windows message.
        self.winId()
        self._init_status_tooltip()

        self.load_config()

        # Показать приветственное окно, если не отключено
        if self.config.get("show_update_info", True):
            dlg = WelcomeDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                if dlg.checkbox.isChecked():
                    self.config["show_update_info"] = False
                if dlg.start_guide_requested:
                    self.config["first_run_guide_completed"] = False
                    self.config["first_run_guide_pending"] = True
                else:
                    self.config["first_run_guide_completed"] = True
                    self.config["first_run_guide_pending"] = False
                self.save_config()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.central_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.central_widget.customContextMenuRequested.connect(
            lambda pos: self.show_main_context_menu(self.central_widget.mapToGlobal(pos))
        )
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 45, 5, 5)
        self.central_widget.setLayout(self.main_layout)

        self.hotkeys_mode = False
        self.force_quit = False
        self._guide_active = False
        self._guide_step_index = 0
        self._guide_effect_widget = None
        self._guide_bubble = None
        self._guide_waiting_action = None
        self._guide_target_animation = None
        self._guide_step_timer = QTimer(self)
        self._guide_step_timer.setSingleShot(True)
        self._guide_step_timer.timeout.connect(self._show_guide_step)
        self.init_ui()

        self.create_tray_icon()
        QTimer.singleShot(700, self._maybe_start_first_run_guide)

        # Подписка на события хоткеев из потоков
        try:
            hotkey_dispatcher.triggered.connect(self._invoke_callback_safely)
        except Exception:
            pass

        # Подписка на ошибки регистрации хоткеев
        try:
            hotkey_error_dispatcher.registration_failed.connect(self._on_hotkey_registration_failed)
        except Exception:
            pass

        # Слушатели для горячих клавиш копирования и перевода (значения берутся из настроек)
        copy_hotkey = self.config.get("copy_hotkey", "")
        if copy_hotkey:
            self.copy_hotkey_thread = HotkeyListenerThread(copy_hotkey, self.launch_copy, hotkey_id=1)
            self.copy_hotkey_thread.start()
        translate_hotkey = self.config.get("translate_hotkey", "")
        if translate_hotkey:
            self.translate_hotkey_thread = HotkeyListenerThread(translate_hotkey, self.launch_translate, hotkey_id=2)
            self.translate_hotkey_thread.start()

        fullscreen_translate_hotkey = self.config.get("fullscreen_translate_hotkey", "")
        if fullscreen_translate_hotkey:
            self.fullscreen_translate_hotkey_thread = HotkeyListenerThread(fullscreen_translate_hotkey, self.launch_fullscreen_translate, hotkey_id=3)
            self.fullscreen_translate_hotkey_thread.start()

        translate_selection_hotkey = self.config.get("translate_selection_hotkey", "")
        if translate_selection_hotkey:
            self.translate_selection_hotkey_thread = HotkeyListenerThread(translate_selection_hotkey, self.launch_translate_selection, hotkey_id=4)
            self.translate_selection_hotkey_thread.start()

        self.HotkeyListenerThread = HotkeyListenerThread

        self.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

    def load_config(self):
        config_path = get_data_file("config.json")
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8-sig") as f:
                self.config = json.load(f)
        else:
            self.config = DEFAULT_CONFIG.copy()
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            invalidate_config_cache()
        # Извлекаем значения с дефолтами из DEFAULT_CONFIG
        self.current_theme = self.config.get("theme", DEFAULT_CONFIG["theme"])
        raw_interface_language = self.config.get("interface_language", DEFAULT_CONFIG["interface_language"])
        self.current_interface_language = normalize_interface_language(
            raw_interface_language
        )
        self.config["interface_language"] = self.current_interface_language
        stored_autostart = self.config.get("autostart", DEFAULT_CONFIG["autostart"])
        stored_autostart_backend = self.config.get("autostart_backend")
        self.autostart = self.sync_autostart_state(repair_stale=True)
        self.translation_mode = self.config.get("translation_mode", LANGUAGES[self.current_interface_language][0])
        self.start_minimized = self.config.get("start_minimized", DEFAULT_CONFIG["start_minimized"])
        if (
            raw_interface_language != self.current_interface_language
            or stored_autostart != self.autostart
            or stored_autostart_backend != AUTOSTART_BACKEND
        ):
            self.save_config()

    def save_config(self):
        self.config["theme"] = self.current_theme
        self.config["interface_language"] = self.current_interface_language
        self.config["autostart"] = getattr(self, "autostart", False)
        self.config["autostart_backend"] = AUTOSTART_BACKEND
        self.config["translation_mode"] = getattr(self, "translation_mode",
                                                  LANGUAGES[self.current_interface_language][0])
        self.config["start_minimized"] = getattr(self, "start_minimized", False)
        config_path = get_data_file("config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)
        invalidate_config_cache()  # Сбрасываем кэш после записи

    def sync_autostart_state(self, repair_stale=False):
        """Sync config with the real Startup folder shortcut."""
        shortcut_info = _read_autostart_shortcut()
        stored_autostart = bool(self.config.get("autostart", DEFAULT_CONFIG["autostart"]))
        stored_backend = self.config.get("autostart_backend")
        enabled = False
        if shortcut_info:
            if _autostart_shortcut_matches_current(shortcut_info):
                enabled = True
            elif repair_stale and getattr(sys, "frozen", False):
                # A stale ClicknTranslate shortcut means the user wanted autostart,
                # but the path changed after moving/updating the portable app.
                enabled = self.set_autostart(True)
            else:
                enabled = False
        elif repair_stale and stored_autostart and stored_backend != AUTOSTART_BACKEND:
            enabled = self.set_autostart(True)
        self.autostart = enabled
        self.config["autostart"] = enabled
        self.config["autostart_backend"] = AUTOSTART_BACKEND
        return enabled

    def set_autostart(self, enable: bool):
        try:
            _write_autostart_command(bool(enable))
            actual = _autostart_shortcut_matches_current(_read_autostart_shortcut())
            self.autostart = bool(actual)
            self.config["autostart"] = self.autostart
            self.config["autostart_backend"] = AUTOSTART_BACKEND
            return self.autostart
        except Exception as e:
            print("Error setting autostart:", e)
            self.autostart = False
            self.config["autostart"] = False
            self.config["autostart_backend"] = AUTOSTART_BACKEND
            return False

    def init_ui(self):
        self.title_bar = QLabel(self)
        self.title_bar.setText(INTERFACE_TEXT[self.current_interface_language]["title"])
        self.title_bar.setGeometry(0, 0, self.width(), 40)
        self.title_bar.setAlignment(Qt.AlignCenter)

        self.flag_button = QPushButton(self)
        self.flag_button.setStyleSheet("background-color: transparent; border: none;")
        self.flag_button.setGeometry(10, 5, 30, 30)
        self.flag_button.clicked.connect(self.show_interface_language_menu)
        self.update_interface_language_button()

        self.theme_button = QPushButton(self)
        self.update_theme_icon()
        self.theme_button.setToolTip(ui_text(self.current_interface_language, "theme"))
        self.theme_button.setStyleSheet("background-color: transparent; border: none;")
        self.theme_button.setGeometry(50, 5, 30, 30)
        self.theme_button.clicked.connect(self.toggle_theme)

        self.minimize_button = QPushButton(self)
        self.minimize_button.setText("‒")
        self.minimize_button.setToolTip(ui_text(self.current_interface_language, "minimize"))
        self.minimize_button.setStyleSheet("background-color: transparent; border: none;")
        self.minimize_button.setGeometry(self.width() - 70, 5, 30, 30)
        self.minimize_button.clicked.connect(self.showMinimized)

        self.document_button = QPushButton(self)
        self.document_button.setToolTip(doc_text(self.current_interface_language, "title"))
        self.document_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: rgba(197, 179, 233, 42);
            }
        """)
        self.document_button.setGeometry(self.width() - 190, 5, 30, 30)
        self.document_button.setIconSize(QSize(26, 26))
        self.document_button.clicked.connect(lambda _checked=False: self.open_document_translation())
        self.update_document_icon()

        # Кнопка помощи (FAQ)
        self.help_button = QPushButton(self)
        self.help_button.setToolTip(ui_text(self.current_interface_language, "help"))
        self.help_button.setStyleSheet("background-color: transparent; border: none;")
        self.help_button.setGeometry(self.width() - 155, 5, 30, 30)
        self.help_button.clicked.connect(self.show_help_dialog)
        self.update_help_icon()

        self.settings_button = QPushButton(self)
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
        self.settings_button.setStyleSheet("background-color: transparent; border: none;")
        self.settings_button.setGeometry(self.width() - 120, 5, 30, 30)
        self.settings_button.clicked.connect(self.show_settings)

        self.close_button = QPushButton(self)
        self.close_button.setText("×")
        self.close_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
        self.close_button.setStyleSheet("background-color: transparent; border: none;")
        self.close_button.setGeometry(self.width() - 40, 5, 30, 30)
        self.close_button.clicked.connect(self.close)

        self.show_main_screen()
        self.apply_theme()

    def create_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(QIcon(resource_path("icons/icon.ico")), self)
        self.tray_icon.setToolTip("Click'n'Translate")
        self.update_tray_menu()
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def update_tray_menu(self):
        lang = self.current_interface_language
        tray_menu = QMenu()
        open_action = tray_menu.addAction(ui_text(lang, "tray_open"))
        open_action.triggered.connect(lambda: self.show_window_from_tray(force_show=True))
        copy_action = tray_menu.addAction(ui_text(lang, "tray_copy"))
        copy_action.triggered.connect(self.launch_copy)
        translate_action = tray_menu.addAction(ui_text(lang, "tray_translate"))
        translate_action.triggered.connect(self.launch_translate)
        fullscreen_action = tray_menu.addAction(ui_text(lang, "tray_translate_screen"))
        fullscreen_action.triggered.connect(self.launch_fullscreen_translate)
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction(ui_text(lang, "tray_exit"))
        exit_action.triggered.connect(self.exit_app)
        self.tray_icon.setContextMenu(tray_menu)

    def on_tray_icon_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window_from_tray()

    def show_window_from_tray(self, force_show=False):
        if self.isVisible() and not force_show:
            self.hide()
            return
        self.setWindowState(Qt.WindowNoState)
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        if sys.platform == "win32":
            try:
                hwnd = int(self.winId())
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOW)
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            except Exception:
                pass
        QTimer.singleShot(250, self._maybe_start_first_run_guide)

    def _maybe_start_first_run_guide(self):
        if not self.config.get("first_run_guide_pending", DEFAULT_CONFIG["first_run_guide_pending"]):
            return
        if self.config.get("first_run_guide_completed", DEFAULT_CONFIG["first_run_guide_completed"]):
            return
        if self._guide_active:
            return
        if not self.isVisible():
            return
        self._guide_active = True
        self._guide_step_index = 0
        self._schedule_guide_step(0)

    def _schedule_guide_step(self, delay_ms=0):
        if not self._guide_active:
            return
        self._guide_step_timer.stop()
        self._guide_step_timer.start(max(0, int(delay_ms)))

    def _guide_steps(self):
        return guide_text(self.current_interface_language)["steps"]

    def _guide_current_action(self):
        steps = self._guide_steps()
        if not steps or self._guide_step_index >= len(steps):
            return None
        return steps[self._guide_step_index][0]

    def _guide_target_widget(self, action):
        if action == "language":
            return getattr(self, "flag_button", None)
        if action == "theme":
            return getattr(self, "theme_button", None)
        if action == "help":
            return getattr(self, "help_button", None)
        if action in ("settings", "back_home"):
            return getattr(self, "settings_button", None)

        settings_window = getattr(self, "settings_window", None)
        if settings_window is None:
            return None
        if action == "ocr_engine":
            return getattr(settings_window, "ocr_engine_combo", None)
        if action == "translator":
            return getattr(settings_window, "translator_combo", None)
        if action == "hotkeys":
            return getattr(settings_window, "hotkeys_button", None)
        return None

    def _show_guide_step(self):
        if not self._guide_active:
            return
        steps = self._guide_steps()
        if self._guide_step_index >= len(steps):
            self._finish_first_run_guide()
            return

        action, title, body = steps[self._guide_step_index]
        target = self._guide_target_widget(action)
        if target is None or not target.isVisible():
            self._schedule_guide_step(250)
            return

        self._highlight_guide_target(target, action)
        self._ensure_guide_bubble()
        text = guide_text(self.current_interface_language)
        self._guide_progress.setText(text["progress"].format(
            current=self._guide_step_index + 1,
            total=len(steps),
        ))
        self._guide_title.setText(title)
        self._guide_body.setText(body)
        self._guide_hint.setText(text["click_hint"])
        if hasattr(self, "_guide_skip_btn"):
            self._guide_skip_btn.setText(text["skip"])
        self._position_guide_bubble(target)
        self._guide_bubble.show()
        self._guide_bubble.raise_()

    def _ensure_guide_bubble(self):
        if self._guide_bubble is not None:
            return
        self._guide_bubble = QFrame(self)
        self._guide_bubble.setObjectName("firstRunGuideBubble")
        self._guide_bubble.setFixedSize(390, 168)
        self._guide_bubble.setStyleSheet("""
            QFrame#firstRunGuideBubble {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #151927, stop:1 #26183a);
                border: 1px solid rgba(197, 179, 233, 185);
                border-radius: 16px;
            }
            QLabel#firstRunGuideProgress {
                color: #c5b3e9;
                font-size: 12px;
                font-weight: 900;
            }
            QLabel#firstRunGuideTitle {
                color: #ffffff;
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#firstRunGuideBody {
                color: #d8d2e8;
                font-size: 15px;
                line-height: 1.35;
            }
            QLabel#firstRunGuideHint {
                color: #c5b3e9;
                background: transparent;
                border: none;
                padding: 5px 0px;
                font-size: 13px;
                font-weight: 900;
            }
            QPushButton#firstRunGuideSkip {
                background: rgba(255, 255, 255, 14);
                color: #d8d2e8;
                border: 1px solid rgba(197, 179, 233, 70);
                border-radius: 9px;
                padding: 5px 12px;
                font-size: 13px;
                font-weight: 900;
            }
            QPushButton#firstRunGuideSkip:hover {
                background: rgba(197, 179, 233, 42);
                color: #ffffff;
            }
        """)
        layout = QVBoxLayout(self._guide_bubble)
        layout.setContentsMargins(15, 11, 15, 11)
        layout.setSpacing(5)

        top_row = QHBoxLayout()
        self._guide_title = QLabel()
        self._guide_title.setObjectName("firstRunGuideTitle")
        self._guide_title.setWordWrap(False)
        top_row.addWidget(self._guide_title)
        top_row.addStretch()
        self._guide_progress = QLabel()
        self._guide_progress.setObjectName("firstRunGuideProgress")
        top_row.addWidget(self._guide_progress)
        layout.addLayout(top_row)

        self._guide_body = QLabel()
        self._guide_body.setObjectName("firstRunGuideBody")
        self._guide_body.setWordWrap(True)
        self._guide_body.setMinimumHeight(66)
        layout.addWidget(self._guide_body)

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self._guide_hint = QLabel()
        self._guide_hint.setObjectName("firstRunGuideHint")
        self._guide_hint.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._guide_hint.setMinimumWidth(150)
        self._guide_hint.setMaximumWidth(215)
        bottom_row.addWidget(self._guide_hint)
        bottom_row.addStretch()

        self._guide_skip_btn = QPushButton()
        self._guide_skip_btn.setObjectName("firstRunGuideSkip")
        self._guide_skip_btn.setMinimumWidth(118)
        self._guide_skip_btn.setMaximumWidth(165)
        self._guide_skip_btn.clicked.connect(self.skip_current_guide_step)
        bottom_row.addWidget(self._guide_skip_btn)
        layout.addLayout(bottom_row)

    def _position_guide_bubble(self, target):
        if self._guide_bubble is None:
            return
        target_pos = target.mapTo(self, QtCore.QPoint(0, 0))
        bubble_w = self._guide_bubble.width()
        bubble_h = self._guide_bubble.height()
        margin = 12

        if target_pos.y() < 55:
            x = target_pos.x() + target.width() + 10
            y = 48
        elif target_pos.x() > self.width() // 2:
            x = target_pos.x() - bubble_w - 12
            y = target_pos.y() - 8
        else:
            x = target_pos.x() + target.width() + 12
            y = target_pos.y() - 8

        x = max(margin, min(x, self.width() - bubble_w - margin))
        y = max(48, min(y, self.height() - bubble_h - margin))
        self._guide_bubble.move(x, y)

    def _highlight_guide_target(self, target, action):
        if self._guide_target_animation is not None:
            try:
                self._guide_target_animation.stop()
            except Exception:
                pass
            self._guide_target_animation = None
        if self._guide_effect_widget is not None and self._guide_effect_widget is not target:
            try:
                self._guide_effect_widget.removeEventFilter(self)
                self._guide_effect_widget.setGraphicsEffect(None)
            except Exception:
                pass
        self._guide_effect_widget = target
        self._guide_waiting_action = action

        try:
            target.removeEventFilter(self)
        except Exception:
            pass
        if action in ("ocr_engine", "translator"):
            target.installEventFilter(self)

        glow = QGraphicsDropShadowEffect(target)
        glow.setOffset(0, 0)
        glow.setColor(QColor(197, 179, 233, 230))
        glow.setBlurRadius(20)
        target.setGraphicsEffect(glow)

        animation = QtCore.QPropertyAnimation(glow, b"blurRadius", self)
        animation.setStartValue(12)
        animation.setEndValue(34)
        animation.setDuration(900)
        animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        animation.setLoopCount(-1)
        animation.start()
        self._guide_target_animation = animation

    def _complete_guide_step(self, action):
        if not self._guide_active:
            return
        if action != self._guide_current_action():
            return
        self._guide_step_index += 1
        self._schedule_guide_step(120)

    def skip_current_guide_step(self):
        if not self._guide_active:
            return
        action = self._guide_current_action()
        self._guide_step_index += 1
        if action == "settings" and getattr(self, "settings_window", None) is None:
            self.show_settings()
        self._schedule_guide_step(80)

    def skip_first_run_guide(self):
        self.config["first_run_guide_completed"] = True
        self.config["first_run_guide_pending"] = False
        self.save_config()
        self._guide_active = False
        self._guide_waiting_action = None
        self._guide_step_timer.stop()

        if self._guide_effect_widget is not None:
            try:
                self._guide_effect_widget.removeEventFilter(self)
                self._guide_effect_widget.setGraphicsEffect(None)
            except Exception:
                pass
        self._guide_effect_widget = None

        if self._guide_target_animation is not None:
            try:
                self._guide_target_animation.stop()
            except Exception:
                pass
            self._guide_target_animation = None

        if self._guide_bubble is not None:
            self._guide_bubble.hide()

    def _finish_first_run_guide(self):
        if not self._guide_active:
            return
        self.config["first_run_guide_completed"] = True
        self.config["first_run_guide_pending"] = False
        self.save_config()
        self._guide_active = False
        self._guide_waiting_action = None
        self._guide_step_timer.stop()

        if self._guide_effect_widget is not None:
            try:
                self._guide_effect_widget.removeEventFilter(self)
                self._guide_effect_widget.setGraphicsEffect(None)
            except Exception:
                pass
        self._guide_effect_widget = None
        if self._guide_target_animation is not None:
            try:
                self._guide_target_animation.stop()
            except Exception:
                pass
            self._guide_target_animation = None

        self._ensure_guide_bubble()
        text = guide_text(self.current_interface_language)
        self._guide_progress.setText("")
        self._guide_title.setText(text["done_title"])
        self._guide_body.setText(text["done_body"])
        self._guide_hint.setText("")
        self._guide_bubble.move(
            max(12, (self.width() - self._guide_bubble.width()) // 2),
            max(48, (self.height() - self._guide_bubble.height()) // 2),
        )
        self._guide_bubble.show()
        self._guide_bubble.raise_()
        QTimer.singleShot(1800, self._hide_guide_bubble)

    def _hide_guide_bubble(self):
        if self._guide_bubble is not None:
            self._guide_bubble.hide()

    def eventFilter(self, watched, event):
        if (
            self._guide_active
            and watched is self._guide_effect_widget
            and event.type() == QtCore.QEvent.MouseButtonPress
            and self._guide_waiting_action in ("ocr_engine", "translator")
        ):
            action = self._guide_waiting_action
            QTimer.singleShot(180, lambda: self._complete_guide_step(action))
        return super().eventFilter(watched, event)

    def nativeEvent(self, eventType, message):
        event_name = eventType.decode("utf-8", "ignore") if isinstance(eventType, bytes) else str(eventType)
        if _SHOW_WINDOW_MESSAGE_ID and event_name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == _SHOW_WINDOW_MESSAGE_ID:
                    QTimer.singleShot(0, _show_running_instance)
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def _start_external(self, script_or_exe, *args):
        """Launch helper that works both in dev (python script) and frozen (exe)."""
        if getattr(sys, 'frozen', False):
            # В собранной версии просто перезапускаем тот же exe с нужным параметром
            subprocess.Popen([sys.executable, *args])
        else:
            # В режиме разработки запускаем python-скрипт
            subprocess.Popen([sys.executable, script_or_exe, *args])

    def launch_ocr(self):
        print("launch_ocr called")
        if hasattr(self, "source_lang"):
            src_text = self.source_lang.currentText().lower()
            lang = "en" if ("english" in src_text or "английский" in src_text) else "ru"
        else:
            lang = self.config.get("ocr_language", self.current_interface_language)
        try:
            # Lazy import to avoid startup penalty
            from ocr import run_screen_capture
            self.hide()
            # run overlay in current QApplication (non-blocking)
            run_screen_capture(mode="ocr")
        except Exception as e:
            print(f"Error launching OCR: {e}")
            # fallback to previous behavior
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "ocr", lang)
            else:
                self._start_external("ocr.py", lang)
            self.hide()

    def launch_copy(self):
        print("launch_copy called")
        try:
            from ocr import run_screen_capture
            # Проверяем настройку - сворачивать ли окно
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()
            run_screen_capture(mode="copy")
        except Exception as e:
            print(f"Error launching copy: {e}")
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "copy")
            else:
                self._start_external("ocr.py", "copy")
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()

    def launch_translate(self):
        print("launch_translate called")
        try:
            from ocr import run_screen_capture
            # Проверяем настройку - сворачивать ли окно
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()
            run_screen_capture(mode="translate")
        except Exception as e:
            print(f"Error launching translate: {e}")
            if getattr(sys, 'frozen', False):
                self._start_external("ocr.py", "translate")
            else:
                self._start_external("ocr.py", "translate")
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()

    def launch_fullscreen_translate(self):
        print("launch_fullscreen_translate called")
        try:
            from ocr import run_fullscreen_translate
            if not self.config.get("keep_visible_on_ocr", False):
                self.hide()

            def _do_translate():
                try:
                    run_fullscreen_translate()
                except Exception as e:
                    print(f"Error in fullscreen translate: {e}")
                    import traceback
                    traceback.print_exc()

            # Small delay to ensure window is hidden before screenshot
            QTimer.singleShot(150, _do_translate)
        except Exception as e:
            print(f"Error launching fullscreen translate: {e}")
            import traceback
            traceback.print_exc()

    # Signal to show/hide status tooltip
    _show_status_signal = QtCore.pyqtSignal(str)
    _hide_status_signal = QtCore.pyqtSignal()

    def _init_status_tooltip(self):
        """Initialize floating status tooltip."""
        from PyQt5.QtWidgets import QLabel
        self._status_label = QLabel()
        self._status_label.setWindowFlags(Qt.ToolTip | Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self._status_label.setStyleSheet(
            "QLabel { background-color: #1a1a2e; color: #e0e0e0; padding: 8px 16px; "
            "border: 1px solid #550000; border-radius: 6px; font-size: 14px; }"
        )
        self._status_label.hide()
        self._show_status_signal.connect(self._on_show_status)
        self._hide_status_signal.connect(self._on_hide_status)

    def _on_show_status(self, text):
        from PyQt5.QtGui import QCursor
        self._status_label.setText(text)
        self._status_label.adjustSize()
        pos = QCursor.pos()
        self._status_label.move(pos.x() + 15, pos.y() + 15)
        self._status_label.show()

    def _on_hide_status(self):
        self._status_label.hide()

    def launch_translate_selection(self):
        """Translate currently selected text: simulate Ctrl+C, read clipboard, translate, show dialog."""
        print("launch_translate_selection called")

        def _do_copy_and_translate():
            lang = self.config.get("interface_language", "ru")
            try:
                # Release all modifier keys first
                KEYEVENTF_KEYUP = 0x0002
                for vk in (0x11, 0x12, 0x10, 0x5B, 0x5C):
                    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.35)
                # Clear clipboard, then Ctrl+C to capture selection
                pyperclip.copy("")
                simulate_copy()
                time.sleep(0.25)
                text = pyperclip.paste()
                if not text or not text.strip():
                    time.sleep(0.3)
                    text = pyperclip.paste()
                if not text or not text.strip():
                    lang = self.config.get("interface_language", "ru")
                    no_text = ui_text(lang, "no_text_selected")
                    self._show_status_signal.emit(no_text)
                    time.sleep(1.5)
                    self._hide_status_signal.emit()
                    return
                text = text.strip()
                # Show status
                lang = self.config.get("interface_language", "ru")
                status_msg = ui_text(lang, "translating")
                self._show_status_signal.emit(status_msg)
                source_code = detect_language_code(text)
                target_code = default_target_for_source(source_code)
                print(f"[SEL] translating {source_code}->{target_code}, {len(text)} chars...")
                from translater import translate_text
                translated = translate_text(text, source_code, target_code)
                self._hide_status_signal.emit()
                print(f"[SEL] result: {len(translated) if translated else 0} chars")
                if not translated:
                    return
                theme = self.config.get("theme", "Темная")
                auto_copy = self.config.get("copy_translated_text", False)
                self._show_selection_signal.emit(translated, auto_copy, lang, theme)
            except Exception as e:
                err_msg = ui_text(lang, "translation_error")
                self._show_status_signal.emit(f"{err_msg}: {e}")
                print(f"Error in translate_selection: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(3)
                self._hide_status_signal.emit()

        threading.Thread(target=_do_copy_and_translate, daemon=True).start()

    def _show_selection_translation(self, translated, auto_copy, lang, theme):
        """Show translation dialog from selection (called in UI thread)."""
        try:
            show_translation_dialog(self, translated, auto_copy=auto_copy, lang=lang, theme=theme)
            if auto_copy:
                pyperclip.copy(translated)
                save_copy_history(translated)
        except Exception as e:
            print(f"Error showing translation dialog: {e}")

    def restart_hotkey_listener(self):
        self.hotkey_thread = HotkeyListenerThread(self.config.get("ocr_hotkeys", "Ctrl+O"), self.launch_ocr)
        self.hotkey_thread.start()

    def apply_theme(self):
        theme = THEMES[self.current_theme]
        # Настроим стиль скроллбара в зависимости от темы
        # Настроим стиль скроллбара в зависимости от темы (как в FAQ)
        scrollbar_bg = theme['button_background']
        scrollbar_handle = '#7A5FA1'  # Фиолетовый
        scrollbar_handle_hover = '#9A7FC1'
        style_sheet = f"""
            QMainWindow {{
                background-color: {theme['background']};
            }}
            QLabel {{
                color: {theme['text_color']};
                font-size: 16px;
            }}
            QComboBox {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: none;
                padding: 5px;
                font-size: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: none;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {theme['item_hover_background']};
                color: {theme['item_hover_color']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {theme['item_selected_background']};
                color: {theme['item_selected_color']};
            }}
            QPushButton {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: 2px solid #C5B3E9;
                padding: 10px;
                font-size: 14px;
            }}
            QLineEdit, QTextEdit {{
                background-color: {theme['button_background']};
                color: {theme['text_color']};
                border: 1px solid #550000;
                padding: 5px;
                font-size: 14px;
            }}
            QTextEdit QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 12px;
                margin: 4px 2px 4px 2px;
                border-radius: 6px;
            }}
            QTextEdit QScrollBar::handle:vertical {{
                background: {scrollbar_handle};
                min-height: 30px;
                border-radius: 5px;
            }}
            QTextEdit QScrollBar::handle:vertical:hover {{
                background: {scrollbar_handle_hover};
            }}
            QTextEdit QScrollBar::add-line:vertical, QTextEdit QScrollBar::sub-line:vertical {{
                height: 0;
                background: none;
            }}
            QTextEdit QScrollBar::add-page:vertical, QTextEdit QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """
        self.setStyleSheet(style_sheet)
        if hasattr(self, "title_bar"):
            header_bg = "#c0c0c0" if self.current_theme == "Светлая" else theme['button_background']
            self.title_bar.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {theme['text_color']}; background-color: {header_bg};"
            )
        if hasattr(self, "minimize_button") and hasattr(self, "close_button"):
            if self.current_theme == "Светлая":
                self.minimize_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #000000;
                        font-size: 16px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #00aa00;
                    }
                """)
                self.close_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #000000;
                        font-size: 20px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #aa0000;
                    }
                """)
            else:
                self.minimize_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: white;
                        font-size: 16px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #00ff00;
                    }
                """)
                self.close_button.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: white;
                        font-size: 20px;
                        border: none;
                    }
                    QPushButton:hover {
                        color: #ff3333;
                    }
                """)
        # Обновить иконку кнопки помощи
        self.update_help_icon()
        self.update_theme_icon()
        self.update_document_icon()
        if hasattr(self, "settings_button"):
            if self.settings_window is None:
                if self.current_theme == "Темная":
                    self.settings_button.setIcon(QIcon(resource_path("icons/settings_light.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
                else:
                    self.settings_button.setIcon(QIcon(resource_path("icons/settings_dark.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
            else:
                if self.current_theme == "Темная":
                    self.settings_button.setIcon(QIcon(resource_path("icons/light_home.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
                else:
                    self.settings_button.setIcon(QIcon(resource_path("icons/dark_home.png")))
                    self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])

    def update_theme_icon(self):
        icon_path = resource_path("icons/sun.png") if self.current_theme == "Темная" else resource_path("icons/moon.png")
        self.theme_button.setIcon(QIcon(icon_path))

    def update_help_icon(self):
        """Обновить иконку кнопки помощи в зависимости от темы."""
        if hasattr(self, "help_button"):
            if self.current_theme == "Темная":
                self.help_button.setIcon(QIcon(resource_path("icons/faq_black_theme.png")))
            else:
                self.help_button.setIcon(QIcon(resource_path("icons/faq_white_theme.png")))

    def update_document_icon(self):
        if hasattr(self, "document_button"):
            self.document_button.setIcon(document_translation_icon(self.current_theme))

    def toggle_theme(self):
        self.current_theme = "Светлая" if self.current_theme == "Темная" else "Темная"
        self.save_config()
        self.apply_theme()
        self.update_theme_icon()
        if self.settings_window is not None:
            self.settings_window.apply_theme()
        if self.document_dialog is not None and self.document_dialog.isVisible():
            self.document_dialog.refresh_theme(self.current_theme)
        self._complete_guide_step("theme")

    def toggle_language(self):
        codes = [option["code"] for option in INTERFACE_LANGUAGE_OPTIONS]
        index = codes.index(self.current_interface_language) if self.current_interface_language in codes else 0
        self.set_interface_language(codes[(index + 1) % len(codes)])

    def update_interface_language_button(self):
        option = get_interface_language_option(self.current_interface_language)
        self.flag_button.setIcon(QIcon(resource_path(option["icon"])))
        self.flag_button.setIconSize(QSize(24, 24))
        self.flag_button.setToolTip(ui_text(self.current_interface_language, "choose_interface_language"))

    def refresh_interface_language_ui(self):
        lang = self.current_interface_language
        if hasattr(self, "title_bar"):
            self.title_bar.setText(INTERFACE_TEXT[lang]["title"])
        if hasattr(self, "flag_button"):
            self.update_interface_language_button()
        if hasattr(self, "theme_button"):
            self.theme_button.setToolTip(ui_text(lang, "theme"))
        if hasattr(self, "minimize_button"):
            self.minimize_button.setToolTip(ui_text(lang, "minimize"))
        if hasattr(self, "help_button"):
            self.help_button.setToolTip(ui_text(lang, "help"))
        if hasattr(self, "document_button"):
            self.document_button.setToolTip(doc_text(lang, "title"))
        if hasattr(self, "settings_button"):
            key = "back" if getattr(self, "settings_window", None) is not None else "settings"
            self.settings_button.setToolTip(INTERFACE_TEXT[lang][key])
        if hasattr(self, "close_button"):
            self.close_button.setToolTip(INTERFACE_TEXT[lang]["back"])
        if hasattr(self, "tray_icon"):
            self.update_tray_menu()

    def show_interface_language_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #11151d;
                color: #ffffff;
                border: 1px solid #54617a;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 7px 20px 7px 10px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background-color: #314968;
            }
            QMenu::indicator {
                width: 0px;
            }
        """)
        for option in INTERFACE_LANGUAGE_OPTIONS:
            selected = option["code"] == self.current_interface_language
            action = menu.addAction(QIcon(resource_path(option["icon"])), ("• " if selected else "  ") + option["name"])
            action.triggered.connect(lambda _checked=False, code=option["code"]: self.set_interface_language(code))
        menu.exec_(self.flag_button.mapToGlobal(self.flag_button.rect().bottomLeft()))
        self._complete_guide_step("language")

    def set_interface_language(self, language_code):
        language_code = normalize_interface_language(language_code)
        if language_code == self.current_interface_language:
            self.refresh_interface_language_ui()
            return
        self.current_interface_language = language_code
        self.config["interface_language"] = language_code
        self.save_config()
        self.refresh_interface_language_ui()
        if self.settings_window is not None:
            self.settings_window.update_language()
        else:
            self.show_main_screen()
        if self.document_dialog is not None and self.document_dialog.isVisible():
            self.document_dialog.refresh_language(language_code)
        self.apply_theme()
        self.update_theme_icon()

    def show_help_dialog(self):
        """Показать окно помощи с описанием переводчиков и OCR."""
        lang = self.current_interface_language
        theme = self.current_theme

        dialog = QDialog(self)
        dialog.setWindowTitle(help_action_text(lang, "title"))
        dialog.setFixedSize(610, 620)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        dialog.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        icon = QLabel("?")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(38, 38)
        icon.setStyleSheet("""
            QLabel {
                color: #111827;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #dfd4ff, stop:1 #8f6fd1);
                border-radius: 14px;
                font-size: 19px;
                font-weight: 900;
            }
        """)
        title_row.addWidget(icon)

        title_stack = QVBoxLayout()
        title_stack.setSpacing(0)
        title_label = QLabel(help_action_text(lang, "title"))
        title_label.setStyleSheet("font-size: 21px; font-weight: 900; color: #ffffff;")
        subtitle_label = QLabel("Click'n'Translate")
        subtitle_label.setStyleSheet("font-size: 12px; font-weight: 800; color: #a994d2;")
        title_stack.addWidget(title_label)
        title_stack.addWidget(subtitle_label)
        title_row.addLayout(title_stack)
        title_row.addStretch()
        layout.addLayout(title_row)

        # Текст FAQ всегда строится из актуального языка интерфейса.
        help_html = help_text(lang)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setHtml(help_html)

        # Стилизация под тему
        if theme == "Темная":
            dialog.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #0f131c, stop:0.55 #15101f, stop:1 #241735);
                }
            """)
            text_edit.setStyleSheet("""
                QTextEdit {
                    background-color: rgba(9, 12, 20, 165);
                    color: #e0e0e0;
                    border: 1px solid rgba(197, 179, 233, 70);
                    border-radius: 16px;
                    padding: 15px;
                    font-size: 13px;
                    line-height: 1.5;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 10px;
                    margin: 4px 2px 4px 2px;
                }
                QScrollBar::handle:vertical {
                    background: #8f6fd1;
                    min-height: 30px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #c5b3e9;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                    background: none;
                }
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                    background: none;
                }
            """)
        else:
            dialog.setStyleSheet("""
                QDialog {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #0f131c, stop:0.55 #15101f, stop:1 #241735);
                }
            """)
            text_edit.setStyleSheet("""
                QTextEdit {
                    background-color: rgba(9, 12, 20, 165);
                    color: #e0e0e0;
                    border: 1px solid rgba(197, 179, 233, 70);
                    border-radius: 16px;
                    padding: 15px;
                    font-size: 13px;
                    line-height: 1.5;
                }
                QScrollBar:vertical {
                    background: transparent;
                    width: 10px;
                    margin: 4px 2px 4px 2px;
                }
                QScrollBar::handle:vertical {
                    background: #8f6fd1;
                    min-height: 30px;
                    border-radius: 5px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #7a5fa1;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0;
                    background: none;
                }
            """)

        layout.addWidget(text_edit)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        guide_btn = QPushButton(help_action_text(lang, "guide"))
        guide_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #c5b3e9, stop:1 #8f6fd1);
                color: #111827;
                border: none;
                border-radius: 12px;
                padding: 10px 22px;
                font-size: 14px;
                font-weight: 900;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #dfd4ff, stop:1 #a681eb);
            }
        """)
        guide_btn.clicked.connect(lambda: self._close_help_and_start_guide(dialog))
        button_row.addWidget(guide_btn)
        button_row.addStretch()

        # Кнопка закрытия
        close_btn = QPushButton(help_action_text(lang, "close"))
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 18);
                color: #efe8ff;
                border: 1px solid rgba(197, 179, 233, 92);
                border-radius: 12px;
                padding: 10px 26px;
                font-size: 14px;
                font-weight: 900;
            }
            QPushButton:hover {
                background-color: rgba(197, 179, 233, 48);
            }
        """)
        close_btn.clicked.connect(dialog.close)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        dialog.exec_()
        self._complete_guide_step("help")

    def _close_help_and_start_guide(self, dialog):
        dialog.accept()
        QTimer.singleShot(120, self.start_first_run_guide)

    def start_first_run_guide(self):
        self.config["first_run_guide_completed"] = False
        self.config["first_run_guide_pending"] = True
        self.save_config()
        self._guide_active = False
        self._guide_step_index = 0
        self._guide_waiting_action = None
        if self._guide_effect_widget is not None:
            try:
                self._guide_effect_widget.removeEventFilter(self)
                self._guide_effect_widget.setGraphicsEffect(None)
            except Exception:
                pass
        self._guide_effect_widget = None
        if self._guide_bubble is not None:
            self._guide_bubble.hide()
        self.show_main_screen()
        self.show_window_from_tray(force_show=True)
        QTimer.singleShot(250, self._maybe_start_first_run_guide)

    def set_settings_button_to_home(self):
        if self.current_theme == "Темная":
            self.settings_button.setIcon(QIcon(resource_path("icons/dark_home.png")))
        else:
            self.settings_button.setIcon(QIcon(resource_path("icons/light_home.png")))
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['back'])
        try:
            self.settings_button.clicked.disconnect()
        except Exception:
            pass
        self.settings_button.clicked.connect(self.show_main_screen)

    def set_settings_button_to_settings(self):
        if self.current_theme == "Темная":
            self.settings_button.setIcon(QIcon(resource_path("icons/settings_light.png")))
        else:
            self.settings_button.setIcon(QIcon(resource_path("icons/settings_dark.png")))
        self.settings_button.setToolTip(INTERFACE_TEXT[self.current_interface_language]['settings'])
        try:
            self.settings_button.clicked.disconnect()
        except Exception:
            pass
        self.settings_button.clicked.connect(self.show_settings)

    def show_main_screen(self):
        self.clear_layout()
        self.settings_window = None
        self.set_settings_button_to_settings()
        
        # Получаем конфиг один раз для всей функции
        cached_config = get_cached_config()
        translator_engine = cached_config.get("translator_engine", "Argos").lower()
        ocr_engine = cached_config.get("ocr_engine", "Windows")
        
        # Отображаем конкретный переводчик
        translator_names = {
            "argos": {"en": "Argos Translate (Offline)", "ru": "Argos Translate (Офлайн)", "es": "Argos Translate (sin conexión)", "de": "Argos Translate (offline)", "fr": "Argos Translate (hors ligne)", "zh": "Argos Translate（离线）"},
            "hymt": {"en": "Hy-MT Translate (Offline)", "ru": "Hy-MT Translate (Офлайн)", "es": "Hy-MT Translate (sin conexión)", "de": "Hy-MT Translate (offline)", "fr": "Hy-MT Translate (hors ligne)", "zh": "Hy-MT Translate（离线）"},
            "google": {"en": "Google Translate", "ru": "Google Translate", "es": "Google Translate", "de": "Google Translate", "fr": "Google Translate", "zh": "Google 翻译"},
            "mymemory": {"en": "MyMemory Translate", "ru": "MyMemory Translate", "es": "MyMemory Translate", "de": "MyMemory Translate", "fr": "MyMemory Translate", "zh": "MyMemory 翻译"},
            "lingva": {"en": "Lingva Translate", "ru": "Lingva Translate", "es": "Lingva Translate", "de": "Lingva Translate", "fr": "Lingva Translate", "zh": "Lingva 翻译"},
            "libretranslate": {"en": "LibreTranslate", "ru": "LibreTranslate", "es": "LibreTranslate", "de": "LibreTranslate", "fr": "LibreTranslate", "zh": "LibreTranslate"}
        }
        
        translator_info = translator_names.get(translator_engine, {"en": "Translation", "ru": "Перевод", "es": "Traducción", "de": "Übersetzung", "fr": "Traduction", "zh": "翻译"})
        lang_label_text = translator_info.get(self.current_interface_language, translator_info["en"])
        
        self.label = QLabel(lang_label_text)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #7A5FA1; font-size: 18px; font-weight: bold; margin-top: 12px; margin-bottom: 8px;")
        self.main_layout.addWidget(self.label)
        self.main_layout.addSpacing(2)
        self.source_lang = QComboBox()
        self.source_lang.addItems(LANGUAGES[self.current_interface_language])
        self.source_lang.setCurrentIndex(0)
        self.source_lang.currentIndexChanged.connect(self.update_languages)
        self.main_layout.addWidget(self.source_lang)
        self.target_lang = QComboBox()
        self.target_lang.addItems(
            [lang for lang in LANGUAGES[self.current_interface_language] if lang != self.source_lang.currentText()]
        )
        self.target_lang.setCurrentIndex(0)
        self.main_layout.addWidget(self.target_lang)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(
            f"{ui_text(self.current_interface_language, 'input_placeholder')}\n{doc_text(self.current_interface_language, 'main_file_hint')}"
        )
        self.text_input.setToolTip(doc_text(self.current_interface_language, "main_file_tooltip"))
        self.text_input.setMinimumHeight(45)
        self.text_input.setMaximumHeight(70)
        self.text_input.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_input.setAcceptDrops(False)
        self.text_input.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.text_input.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text_input.customContextMenuRequested.connect(self._show_text_input_context_menu)
        self.main_layout.addWidget(self.text_input)

        # Кнопка перевода сразу под полем ввода
        self.translate_button = QPushButton(ui_text(self.current_interface_language, "translate_button"))
        self.translate_button.clicked.connect(self.translate_input_text)
        self.translate_button.setStyleSheet("border: 2px solid #C5B3E9; border-radius: 8px; font-size: 16px; padding: 8px 0; background: none; color: #7A5FA1;")
        self.main_layout.addWidget(self.translate_button)

        # --- Блок хоткеев (показываем всегда) ---
        hk_style = "font-size: 13px; color: #888; padding: 0; margin: 0;"
        hk_val = "color: #7A5FA1; font-weight: bold;"
        not_set = "—"
        lang = self.current_interface_language

        copy_hk = self.config.get("copy_hotkey", "") or not_set
        translate_hk = self.config.get("translate_hotkey", "") or not_set
        fs_hk = self.config.get("fullscreen_translate_hotkey", "") or not_set
        sel_hk = self.config.get("translate_selection_hotkey", "") or not_set

        tr_names = {"argos": "Argos", "hymt": "Hy-MT", "google": "Google", "mymemory": "MyMemory", "lingva": "Lingva", "libretranslate": "LibreTranslate"}
        tr_name = tr_names.get(translator_engine, translator_engine.capitalize())

        # Row 1: Copy + OCR translate | OCR engine + Translator
        row1 = QHBoxLayout()
        row1.setSpacing(0)
        r1_left = QLabel(f"{ui_text(lang, 'hotkey_copy')}: <span style='{hk_val}'>{copy_hk}</span> &nbsp; {ui_text(lang, 'hotkey_ocr_translate')}: <span style='{hk_val}'>{translate_hk}</span>")
        r1_left.setStyleSheet(hk_style)
        r1_left.setTextFormat(Qt.RichText)
        row1.addWidget(r1_left, alignment=Qt.AlignLeft)
        row1.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        r1_right = QLabel(f"OCR: <b>{ocr_engine}</b>")
        r1_right.setStyleSheet("font-size: 13px; color: #7A5FA1; margin-right: 8px;")
        r1_right.setTextFormat(Qt.RichText)
        row1.addWidget(r1_right, alignment=Qt.AlignRight)
        self.main_layout.addLayout(row1)

        # Row 2: Fullscreen + Selection | Translator
        row2 = QHBoxLayout()
        row2.setSpacing(0)
        r2_left = QLabel(f"{ui_text(lang, 'hotkey_fullscreen')}: <span style='{hk_val}'>{fs_hk}</span> &nbsp; {ui_text(lang, 'hotkey_selection')}: <span style='{hk_val}'>{sel_hk}</span>")
        r2_left.setStyleSheet(hk_style)
        r2_left.setTextFormat(Qt.RichText)
        row2.addWidget(r2_left, alignment=Qt.AlignLeft)
        row2.addItem(QSpacerItem(10, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        r2_right = QLabel(f"{ui_text(lang, 'translator')}: <b>{tr_name}</b>")
        r2_right.setStyleSheet("font-size: 13px; color: #7A5FA1; margin-right: 8px;")
        r2_right.setTextFormat(Qt.RichText)
        row2.addWidget(r2_right, alignment=Qt.AlignRight)
        self.main_layout.addLayout(row2)

        # Кнопка старт (shadow mode) в самом низу
        start_text = ui_text(self.current_interface_language, "shadow_mode")
        self.start_button = QPushButton(start_text)
        self.start_button.setStyleSheet("border: none; font-size: 16px; padding: 8px 0; background-color: #C5B3E9; color: #111; border-radius: 8px;")
        self.main_layout.addWidget(self.start_button)
        self.start_button.clicked.connect(self.minimize_to_tray)
        self.apply_theme()
        self._complete_guide_step("back_home")

    def show_settings(self):
        self.clear_layout()
        from settings_window import SettingsWindow
        self.settings_window = SettingsWindow(self)
        self.main_layout.addWidget(self.settings_window)
        self.set_settings_button_to_home()
        self.apply_theme()
        self._complete_guide_step("settings")

    def update_languages(self):
        src = self.source_lang.currentText()
        tgt = self.target_lang.currentText()
        available_targets = LANGUAGES[self.current_interface_language][:]
        if src in available_targets:
            available_targets.remove(src)
        self.target_lang.clear()
        self.target_lang.addItems(available_targets)
        if tgt in available_targets:
            self.target_lang.setCurrentText(tgt)
        else:
            self.target_lang.setCurrentIndex(0)

    def clear_layout(self):
        # Удаляем все виджеты и layout'ы из main_layout
        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_nested_layout(item.layout())

    def _clear_nested_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_nested_layout(item.layout())

    def open_document_translation(self, path=None):
        if self.document_dialog is None or not self.document_dialog.isVisible():
            self.document_dialog = DocumentTranslationDialog(self, initial_path=path)
        elif path:
            self.document_dialog.load_file(path)
        self.document_dialog.show()
        self.document_dialog.raise_()
        self.document_dialog.activateWindow()

    def _apply_main_context_menu_style(self, menu):
        if self.current_theme == "Темная":
            menu.setStyleSheet("""
                QMenu {
                    background-color: #11151d;
                    color: #ffffff;
                    border: 1px solid #54617a;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    padding: 7px 20px 7px 10px;
                    border-radius: 6px;
                }
                QMenu::item:selected {
                    background-color: #314968;
                }
            """)
        else:
            menu.setStyleSheet("""
                QMenu {
                    background-color: #ffffff;
                    color: #1f2937;
                    border: 1px solid #c5b3e9;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    padding: 7px 20px 7px 10px;
                    border-radius: 6px;
                }
                QMenu::item:selected {
                    background-color: #e9ddff;
                }
            """)

    def _add_document_context_actions(self, menu):
        lang = self.current_interface_language
        file_action = menu.addAction(doc_text(lang, "context_translate_file"))
        file_action.triggered.connect(self._choose_document_from_main)
        folder_action = menu.addAction(doc_text(lang, "context_choose_folder"))
        folder_action.triggered.connect(self._choose_document_directory_from_main)

    def show_main_context_menu(self, global_pos):
        menu = QMenu(self)
        self._apply_main_context_menu_style(menu)
        self._add_document_context_actions(menu)
        menu.exec_(global_pos)

    def _show_text_input_context_menu(self, pos):
        menu = self.text_input.createStandardContextMenu()
        menu.addSeparator()
        self._add_document_context_actions(menu)
        self._apply_main_context_menu_style(menu)
        menu.exec_(self.text_input.mapToGlobal(pos))

    def _choose_document_from_main(self, initial_dir=""):
        path, _ = QFileDialog.getOpenFileName(
            self,
            doc_text(self.current_interface_language, "attach_file"),
            initial_dir or "",
            document_file_filter(),
        )
        if path:
            self.open_document_translation(path)

    def _choose_document_directory_from_main(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            doc_text(self.current_interface_language, "context_choose_folder"),
            "",
        )
        if directory:
            self._choose_document_from_main(directory)

    def _first_dropped_file(self, event):
        if not event.mimeData().hasUrls():
            return ""
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                return path
        return ""

    def dragEnterEvent(self, event):
        if self._first_dropped_file(event):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        path = self._first_dropped_file(event)
        if path:
            self.open_document_translation(path)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_O and event.modifiers() & Qt.ControlModifier:
            self._choose_document_from_main()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.show_main_context_menu(event.globalPos())
            event.accept()
            return
        if event.button() == Qt.LeftButton and event.y() <= 40:
            self._is_dragging = True
            self._drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self.move(event.globalPos() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            event.accept()

    def _invoke_callback_safely(self, cb):
        try:
            cb()
        except Exception:
            pass

    def _on_hotkey_registration_failed(self, hotkey_str):
        """Показать уведомление, когда хоткей занят другим приложением."""
        lang = self.current_interface_language
        if lang == "ru":
            title = "Горячая клавиша недоступна"
            msg = (f"Не удалось зарегистрировать <b>{hotkey_str}</b>.<br><br>"
                   f"Эта комбинация уже используется браузером или системой "
                   f"(например, Ctrl+Shift+T открывает закрытую вкладку).<br><br>"
                   f"Попробуйте другую комбинацию в настройках.")
        else:
            title = "Hotkey unavailable"
            msg = (f"Failed to register <b>{hotkey_str}</b>.<br><br>"
                   f"This combination is already used by browser or system "
                   f"(e.g., Ctrl+Shift+T reopens closed tab).<br><br>"
                   f"Try a different combination in settings.")

        # Используем QTimer для показа в главном потоке
        QTimer.singleShot(100, lambda: self._show_hotkey_error_dialog(title, msg))

    def _show_hotkey_error_dialog(self, title, msg):
        """Показать диалог ошибки регистрации хоткея."""
        theme = self.current_theme
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setTextFormat(Qt.RichText)
        dialog.setText(msg)
        dialog.setIcon(QMessageBox.Warning)
        dialog.setWindowIcon(QIcon(resource_path("icons/icon.ico")))

        if theme == "Темная":
            dialog.setStyleSheet("""
                QMessageBox { background-color: #121212; }
                QLabel { color: #ffffff; font-size: 14px; }
                QPushButton { background-color: #1e1e1e; color: #ffffff; border: 1px solid #550000; padding: 6px 16px; min-width: 80px; }
                QPushButton:hover { background-color: #333333; }
            """)
        else:
            dialog.setStyleSheet("""
                QMessageBox { background-color: #ffffff; }
                QLabel { color: #000000; font-size: 14px; }
                QPushButton { background-color: #f0f0f0; color: #000000; border: 1px solid #cccccc; padding: 6px 16px; min-width: 80px; }
                QPushButton:hover { background-color: #e0e0e0; }
            """)

        dialog.exec_()

    def closeEvent(self, event):
        if not self.force_quit:
            # Сворачиваем в трей вместо закрытия
            event.ignore()
            self.hide()
            # Опционально: показать уведомление при первом сворачивании (можно добавить позже)
            return

        # Если force_quit=True, то выполняем полноценный выход
        try:
            if hasattr(self, "hotkey_thread") and self.hotkey_thread is not None:
                self.hotkey_thread.stop()
                self.hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping OCR hotkey thread: {e}")
        try:
            if hasattr(self, "copy_hotkey_thread") and self.copy_hotkey_thread is not None:
                self.copy_hotkey_thread.stop()
                self.copy_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping copy hotkey thread: {e}")
        try:
            if hasattr(self, "translate_hotkey_thread") and self.translate_hotkey_thread is not None:
                self.translate_hotkey_thread.stop()
                self.translate_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping translate hotkey thread: {e}")
        try:
            if hasattr(self, "fullscreen_translate_hotkey_thread") and self.fullscreen_translate_hotkey_thread is not None:
                self.fullscreen_translate_hotkey_thread.stop()
                self.fullscreen_translate_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping fullscreen translate hotkey thread: {e}")
        try:
            if hasattr(self, "translate_selection_hotkey_thread") and self.translate_selection_hotkey_thread is not None:
                self.translate_selection_hotkey_thread.stop()
                self.translate_selection_hotkey_thread.join(timeout=0.5)
        except Exception as e:
            print(f"Error stopping selection hotkey thread: {e}")
        self.save_config()
        self.tray_icon.hide()  # Убираем иконку из трея
        event.accept()

    def exit_app(self):
        """Полный выход из приложения (вызывается из трея)."""
        self.force_quit = True
        self.close()
        # Явно завершаем приложение Qt
        QApplication.instance().quit()
        # Принудительный выход из процесса Python
        sys.exit(0)

    def translate_input_text(self):
        text = self.text_input.toPlainText()
        if text:
            source_code = language_code_from_name(self.source_lang.currentText(), self.current_interface_language)
            target_code = language_code_from_name(self.target_lang.currentText(), self.current_interface_language)
            try:
                # Показать прогресс, если потребуется установка моделей Argos
                progress = None
                # Локальный колбэк для обновления статуса
                def _status(msg):
                    nonlocal progress
                    if progress is None:
                        title = ui_text(self.current_interface_language, "installing_language_packages")
                        progress = QProgressDialog(title, None, 0, 0, self)
                        progress.setCancelButton(None)
                        progress.setWindowModality(Qt.WindowModal)
                        progress.setAutoClose(False)
                        # hide ? button
                        try:
                            progress.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
                        except Exception:
                            pass
                        progress.show()
                        QApplication.processEvents()
                    try:
                        progress.setLabelText(str(msg))
                    except Exception:
                        pass
                    QApplication.processEvents()

                # Оборачиваем вызов перевода, передавая колбэк установки моделей
                def _translate_with_progress():
                    return translater.translate_text(text, source_code, target_code, status_callback=_status)

                translated_text = _translate_with_progress()
                if progress is not None:
                    try:
                        progress.close()
                    except Exception:
                        pass
                # Проверяем флаг copy_translated_text из кэша
                config = get_cached_config()
                auto_copy = config.get("copy_translated_text", True)
                lang = config.get("interface_language", "ru")
                theme = config.get("theme", "Темная")
                if auto_copy:
                    pyperclip.copy(translated_text)
                    try:
                        if config.get("copy_history", False):
                            save_copy_history(translated_text)
                    except Exception:
                        pass
                # Показываем универсальный диалог
                show_translation_dialog(self, translated_text, auto_copy=auto_copy, lang=lang, theme=theme)
                if not auto_copy:
                    try:
                        if config.get("copy_history", False):
                            save_copy_history(translated_text)
                    except Exception:
                        pass
            except Exception as e:
                QMessageBox.warning(self, "Ошибка перевода", str(e))

    def minimize_to_tray(self):
        self.hide()

# --- Универсальный диалог перевода ---
def show_translation_dialog(parent, translated_text, auto_copy=True, lang='ru', theme='Темная'):
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton
    is_dark = theme == "Темная"
    bg = "#121212" if is_dark else "#ffffff"
    fg = "#ffffff" if is_dark else "#000000"
    btn_bg = "#1e1e1e" if is_dark else "#f0f0f0"
    btn_border = "#550000" if is_dark else "#cccccc"
    btn_hover = "#333333" if is_dark else "#e0e0e0"

    dlg = QDialog(parent)
    dlg.setWindowTitle("Click'n'Translate")
    dlg.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
    dlg.setWindowIcon(QIcon(resource_path("icons/icon.png")))
    dlg.setMinimumSize(350, 150)
    dlg.setMaximumSize(800, 600)
    dlg.setStyleSheet(f"QDialog {{ background-color: {bg}; }}")

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 12)

    text_edit = QTextEdit()
    text_edit.setPlainText(translated_text)
    text_edit.setReadOnly(True)
    text_edit.setStyleSheet(
        f"QTextEdit {{ background-color: {bg}; color: {fg}; border: none; font-size: 16px; }}"
        f"QScrollBar:vertical {{ background: {bg}; width: 8px; }}"
        f"QScrollBar::handle:vertical {{ background: #555; border-radius: 4px; }}"
    )
    layout.addWidget(text_edit)

    btn_style = (
        f"QPushButton {{ background-color: {btn_bg}; color: {fg}; border: 1px solid {btn_border}; "
        f"padding: 6px 16px; min-width: 80px; font-size: 13px; }}"
        f"QPushButton:hover {{ background-color: {btn_hover}; }}"
    )

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()

    copy_text = ui_text(lang, "copy")
    google_text = ui_text(lang, "google")
    close_text = ui_text(lang, "close")

    if not auto_copy:
        copy_btn = QPushButton(copy_text)
        copy_btn.setStyleSheet(btn_style)
        copy_btn.clicked.connect(lambda: pyperclip.copy(translated_text))
        btn_layout.addWidget(copy_btn)

    google_btn = QPushButton(google_text)
    google_btn.setStyleSheet(btn_style)
    google_btn.clicked.connect(lambda: (webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(translated_text)), dlg.accept()))
    btn_layout.addWidget(google_btn)

    close_btn = QPushButton(close_text)
    close_btn.setStyleSheet(btn_style)
    close_btn.clicked.connect(dlg.accept)
    btn_layout.addWidget(close_btn)

    layout.addLayout(btn_layout)

    # Auto-size based on text length
    lines = translated_text.count('\n') + 1
    text_len = len(translated_text)
    height = min(max(150, lines * 28 + 80, text_len // 2 + 100), 600)
    width = min(max(350, min(text_len * 8, 700)), 800)
    dlg.resize(width, height)

    if auto_copy:
        pyperclip.copy(translated_text)

    dlg.exec_()

if __name__ == "__main__":

    # --- Обработка вызова как OCR подпроцесса -----------------
    if len(sys.argv) > 1 and sys.argv[1] in ("ocr", "copy", "translate"):
        from ocr import run_screen_capture
        mode_arg = sys.argv[1]
        run_screen_capture(mode="ocr" if mode_arg == "ocr" else mode_arg)
        sys.exit(0)

    # Single instance через Windows mutex
    def is_already_running():
        """Проверить через mutex, запущен ли уже экземпляр программы."""
        try:
            # Создаем уникальный mutex
            kernel32 = ctypes.windll.kernel32
            mutex = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
            if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(mutex)
                return True
            # Сохраняем handle чтобы mutex жил пока программа работает
            global _single_instance_mutex
            _single_instance_mutex = mutex
            return False
        except Exception:
            return False

    def bring_existing_to_front():
        """Отправить запущенному экземпляру команду раскрыть главное окно."""
        if not _SHOW_WINDOW_MESSAGE_ID:
            return False
        try:
            return bool(ctypes.windll.user32.PostMessageW(HWND_BROADCAST, _SHOW_WINDOW_MESSAGE_ID, 0, 0))
        except Exception:
            return False

    # Проверяем single instance (не разрешаем запуск нескольких копий)
    if is_already_running():
        # Пытаемся показать существующее окно
        other_install = _other_install_instances()
        if other_install and _confirm_close_other_install(other_install):
            _terminate_instances(other_install)
            if is_already_running():
                bring_existing_to_front()
                sys.exit(0)
        else:
            bring_existing_to_front()
            sys.exit(0)
    
    # Читаем конфиг
    start_minimized = False
    try:
        config_path = get_data_file("config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            start_minimized = config.get("start_minimized", False)
    except Exception:
        pass
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    if _SHOW_WINDOW_MESSAGE_ID:
        try:
            _single_instance_event_filter = _SingleInstanceMessageFilter()
            app.installNativeEventFilter(_single_instance_event_filter)
        except Exception:
            _single_instance_event_filter = None
    # Повышаем приоритет процесса для уменьшения задержек
    try:
        HIGH_PRIORITY_CLASS = 0x00000080
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), HIGH_PRIORITY_CLASS)
    except Exception:
        pass
    # Прогрев OCR, чтобы первый запуск оверлея был быстрее
    try:
        from ocr import warm_up, prepare_overlay
        import logging
        # Логируем настройки при старте
        config = get_cached_config()
        logging.info("=" * 50)
        logging.info("ClicknTranslate Started")
        logging.info(f"OCR Engine: {config.get('ocr_engine', 'Windows').upper()}")
        logging.info(f"Translator: {config.get('translator_engine', 'Google').upper()}")
        logging.info(f"OCR Language: {config.get('last_ocr_language', 'ru').upper()}")
        logging.info("=" * 50)
        warm_up()
        # Подготовим заранее все режимы оверлея
        prepare_overlay("ocr")
        prepare_overlay("copy")
        prepare_overlay("translate")
    except Exception:
        pass
    window = DarkThemeApp()
    _main_window_ref = window
    # Всегда используем window.start_minimized, который инициализирован из config.json
    # Проверку на повторный запуск is_already_running() убрали
    if window.start_minimized:
        window.minimize_to_tray()
    else:
        window.show()
    app.exec_()
