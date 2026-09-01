"""Privacy-safe diagnostics for user initiated bug reports.

The report intentionally excludes clipboard contents, translation/copy history,
document text, API keys and the full configuration file.  A user can inspect
the generated ZIP before attaching it to GitHub or Telegram.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import struct
import sys
import tempfile
import time
import zipfile
from pathlib import Path


MAX_LOG_BYTES = 2 * 1024 * 1024
SAFE_CONFIG_KEYS = (
    "interface_language",
    "theme",
    "ocr_engine",
    "translator_engine",
    "autostart",
    "autostart_backend",
    "start_minimized",
    "update_check_on_launch",
    "allow_online_provider_fallback",
    "copy_history",
    "history",
    "copy_translated_text",
    "restore_clipboard_after_selection",
    "notifications",
    "keep_visible_on_ocr",
    "freeze_screen_on_ocr",
    "dim_screen_during_ocr",
    "ocr_dim_strength",
    "game_capture_interval_ms",
    "game_text_similarity",
    "game_pause_when_inactive",
    "game_show_original_text",
    "game_overlay_opacity",
    "game_translate_source_language",
    "game_translate_target_language",
    "ocr_translate_source_language",
    "ocr_translate_target_language",
    "fullscreen_translate_from",
    "fullscreen_translate_to",
    "selection_translate_source_language",
    "selection_translate_target_language",
    "replace_selection_source_language",
    "replace_selection_target_language",
    "result_window_hidden_modes",
    "copy_hotkey",
    "translate_hotkey",
    "fullscreen_translate_hotkey",
    "translate_selection_hotkey",
    "translate_replace_selection_hotkey",
    "game_translate_hotkey",
    "toggle_window_hotkey",
)


def _portable_root() -> Path:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        # Installed/portable builds run from <root>/app/ClicknTranslateApp.exe.
        if executable.parent.name.lower() == "app":
            return executable.parent.parent
        return executable.parent
    return Path(__file__).resolve().parent


def _redactor() -> tuple[tuple[str, str], ...]:
    replacements: list[tuple[str, str]] = []
    values = {
        os.path.expanduser("~"),
        os.environ.get("USERPROFILE", ""),
        os.environ.get("APPDATA", ""),
        os.environ.get("LOCALAPPDATA", ""),
        tempfile.gettempdir(),
    }
    for value in sorted((item for item in values if item), key=len, reverse=True):
        replacements.append((os.path.normpath(value), "<user-path>"))
        replacements.append((os.path.normpath(value).replace("\\", "/"), "<user-path>"))
    username = os.environ.get("USERNAME") or os.environ.get("USER")
    if username:
        replacements.append((username, "<user>"))
    return tuple(replacements)


def _redact(value: object) -> str:
    text = str(value)
    for source, replacement in _redactor():
        text = re.sub(re.escape(source), replacement, text, flags=re.IGNORECASE)
    # Redact obvious bearer/API tokens that may have reached a third-party log.
    text = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+|api[_-]?key\s*[:=]\s*)[^\s,;]+",
        r"\1<redacted>",
        text,
    )
    return text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_line(label: str, path: Path) -> str:
    if not path.is_file():
        return f"{label}: missing ({_redact(path)})"
    try:
        stat = path.stat()
        return (
            f"{label}: present, bytes={stat.st_size}, "
            f"sha256={_sha256(path)}, path={_redact(path)}"
        )
    except OSError as error:
        return f"{label}: unreadable, path={_redact(path)}, error={_redact(error)}"


def _safe_config(data_root: Path) -> dict[str, object]:
    path = data_root / "config.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        return {"config_status": f"unreadable: {_redact(error)}"}
    if not isinstance(payload, dict):
        return {"config_status": "not an object"}
    return {key: payload.get(key) for key in SAFE_CONFIG_KEYS if key in payload}


def _tail(path: Path, limit: int = MAX_LOG_BYTES) -> bytes:
    with path.open("rb") as source:
        source.seek(0, os.SEEK_END)
        size = source.tell()
        source.seek(max(0, size - limit))
        return source.read()


def _default_output_dir() -> Path:
    # OneDrive often redirects Desktop on Windows. A report placed in Temp is
    # easy to lose immediately after the Explorer window closes, so prefer all
    # common user-visible locations before falling back to Documents.
    candidates = [
        Path(value) / "Desktop"
        for value in (
            os.environ.get("OneDrive", ""),
            os.environ.get("OneDriveConsumer", ""),
            os.environ.get("USERPROFILE", ""),
            str(Path.home()),
        )
        if value
    ]
    root = next((candidate for candidate in candidates if candidate.is_dir()), None)
    if root is None:
        root = Path.home() / "Documents"
    return root / "ClicknTranslate Bug Reports"


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for distribution in (
        "PyQt5",
        "requests",
        "Pillow",
        "pytesseract",
        "easyocr",
        "rapidocr-onnxruntime",
        "argostranslate",
        "psutil",
    ):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not installed"
        except Exception as error:
            versions[distribution] = f"unknown: {_redact(error)}"
    return versions


def _environment_report(root: Path, app_version: str) -> dict[str, object]:
    try:
        disk = shutil.disk_usage(root)
        disk_info = {
            "total_bytes": disk.total,
            "free_bytes": disk.free,
        }
    except OSError as error:
        disk_info = {"error": _redact(error)}
    return {
        "generated_local": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "app_version": app_version,
        "platform": _redact(platform.platform()),
        "windows_version": _redact(platform.win32_ver()),
        "machine": platform.machine(),
        "process_bits": struct.calcsize("P") * 8,
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": _redact(sys.executable),
        "root": _redact(root),
        "display_environment": {
            key: _redact(os.environ.get(key, ""))
            for key in ("LANG", "QT_QPA_PLATFORM", "XDG_SESSION_TYPE", "WAYLAND_DISPLAY", "DISPLAY")
            if os.environ.get(key)
        },
        "disk": disk_info,
        "packages": _package_versions(),
    }


def _send_instructions(report_name: str) -> str:
    return f"""Click'n'Translate bug report

SEND / ОТПРАВКА
1. Attach {report_name} to one of these places:
   GitHub: https://github.com/jabrailkhalil/clickntranslate/issues
   Telegram: https://t.me/jabrail_digital
2. In the message describe what you did, what you expected, and what happened.
3. Add a screenshot or video separately if it helps. Check it for private text first.

1. Прикрепите {report_name} в GitHub Issues или Telegram по ссылкам выше.
2. Опишите: что делали, что ожидали и что произошло.
3. Скриншот или видео прикрепляйте отдельно, предварительно проверив личный текст.

The ZIP excludes clipboard contents, translation/copy history, document text,
OCR images, recognized text and API keys.
"""


def create_bug_report(output_dir: str | os.PathLike[str] | None = None, *, app_version: str = "unknown") -> Path:
    """Create and return a local ZIP that is safe to share with maintainers."""

    root = _portable_root()
    data_root = root / "data"
    destination = Path(output_dir) if output_dir is not None else _default_output_dir()
    destination.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report_dir = destination / f"ClicknTranslate-bug-report-{stamp}"
    counter = 2
    while report_dir.exists():
        report_dir = destination / f"ClicknTranslate-bug-report-{stamp}-{counter}"
        counter += 1
    report_dir.mkdir(parents=True)
    report_path = report_dir / f"ClicknTranslate-bug-report-{stamp}.zip"
    instructions = _send_instructions(report_path.name)
    (report_dir / "HOW_TO_SEND.txt").write_text(instructions, encoding="utf-8")

    launcher = root / "ClicknTranslate.exe"
    inner = root / "app" / "ClicknTranslateApp.exe"
    updater = root / "app" / "_internal" / "ClicknTranslateUpdater.exe"
    lines = [
        "Click'n'Translate diagnostics",
        "Generated by an explicit user action; private text and histories are excluded.",
        "",
        f"generated_local: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"app_version: {app_version}",
        f"platform: {_redact(platform.platform())}",
        f"windows_release: {_redact(platform.win32_ver())}",
        f"machine: {platform.machine()}",
        f"python: {platform.python_version()}",
        f"frozen: {bool(getattr(sys, 'frozen', False))}",
        f"root: {_redact(root)}",
        "",
        _file_line("public_launcher", launcher),
        _file_line("application", inner),
        _file_line("updater", updater),
        "",
        "safe_config:",
        json.dumps(_safe_config(data_root), ensure_ascii=False, indent=2, sort_keys=True),
        "",
        "When reporting the issue, describe:",
        "- steps that caused it",
        "- expected result",
        "- actual result",
        "- whether it happens every time.",
    ]
    environment = _environment_report(root, app_version)
    safe_config = _safe_config(data_root)

    runtime_log = data_root / "logs" / "ocr_debug.log"
    if runtime_log.is_file():
        try:
            runtime_stat = runtime_log.stat()
            lines.extend([
                "",
                "runtime_log: present but intentionally excluded because OCR logs may contain recognized text",
                f"runtime_log_bytes: {runtime_stat.st_size}",
                f"runtime_log_modified_local: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(runtime_stat.st_mtime))}",
            ])
        except OSError:
            lines.extend(["", "runtime_log: present but unreadable and excluded"])

    log_candidates = [
        Path(tempfile.gettempdir()) / "clickntranslate_launcher.log",
        Path(tempfile.gettempdir()) / "clickntranslate_update.log",
        Path(tempfile.gettempdir()) / "clickntranslate_setup_update.log",
    ]
    with zipfile.ZipFile(report_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("report.txt", "\n".join(lines) + "\n")
        archive.writestr("HOW_TO_SEND.txt", instructions)
        archive.writestr(
            "environment.json",
            json.dumps(environment, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        archive.writestr(
            "safe-config.json",
            json.dumps(safe_config, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        used_names: set[str] = set()
        for candidate in log_candidates:
            if not candidate.is_file():
                continue
            try:
                text = _tail(candidate).decode("utf-8", errors="replace")
                safe_text = _redact(text)
            except OSError as error:
                safe_text = f"Could not read log: {_redact(error)}\n"
            name = candidate.name
            if name in used_names:
                name = f"{candidate.parent.name}-{name}"
            used_names.add(name)
            archive.writestr(f"logs/{name}", safe_text)
    return report_path
