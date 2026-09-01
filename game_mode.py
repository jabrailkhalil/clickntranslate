"""Dynamic OCR translation for one or more user-selected screen regions.

The mode intentionally reuses Click'n'Translate's OCR and translation engines.
Its orchestration follows the useful parts shared by open-source game
translators such as Translumo, SubLens and GameLingo: skip visually unchanged
frames, ignore small OCR jitter, pause outside the bound app, and paint the
translation over the source location instead of opening a separate result UI.
"""

from __future__ import annotations

import ctypes
import difflib
import logging
import os
import re
import sys
import threading
import time

from PyQt5 import QtCore, QtGui, QtWidgets

import platform_support
from settings_window import LanguageSwapButton

try:
    from ctypes import wintypes
except ImportError:  # pragma: no cover - only relevant on non-Windows Python builds
    wintypes = None


GAME_TEXT = {
    "en": {
        "title": "Dynamic translation",
        "select": "Select one or more areas whose text should be replaced",
        "select_hint": "Draw every area, then press Start or Enter · Backspace removes the last one",
        "start": "Start",
        "undo": "Undo",
        "selected_count": "Selected: {count}",
        "waiting": "Waiting for new text…",
        "scanning": "Reading the selected area…",
        "translating": "Translating…",
        "paused": "Paused while the target app is inactive",
        "no_text": "No readable text yet",
        "pause": "Pause",
        "resume": "Resume",
        "reselect": "Select another area",
        "close": "Stop dynamic translation",
        "capture_error": "The selected area cannot be captured",
        "ocr_error": "OCR is unavailable for this mode",
        "translation_error": "Translation failed; the mode will retry",
        "wayland_error": "Continuous capture is unavailable through the Wayland screenshot portal. Use an X11 session.",
    },
    "ru": {
        "title": "Динамический перевод",
        "select": "Выделите одну или несколько областей для замены текста",
        "select_hint": "Выделите все области, затем нажмите «Запустить» или Enter · Backspace удаляет последнюю",
        "start": "Запустить",
        "undo": "Назад",
        "selected_count": "Выбрано: {count}",
        "waiting": "Жду новый текст…",
        "scanning": "Читаю выбранную область…",
        "translating": "Перевожу…",
        "paused": "Пауза: целевое окно неактивно",
        "no_text": "Читаемого текста пока нет",
        "pause": "Пауза",
        "resume": "Продолжить",
        "reselect": "Выбрать другую область",
        "close": "Остановить динамический перевод",
        "capture_error": "Не удалось захватить выбранную область",
        "ocr_error": "OCR недоступен для динамического режима",
        "translation_error": "Ошибка перевода — режим повторит попытку",
        "wayland_error": "Динамический захват через портал Wayland недоступен. Используйте сеанс X11.",
    },
    "es": {
        "title": "Traducción dinámica",
        "select": "Selecciona una o varias áreas cuyo texto se reemplazará",
        "select_hint": "Dibuja todas las áreas y pulsa Iniciar o Enter · Retroceso elimina la última",
        "start": "Iniciar",
        "undo": "Deshacer",
        "selected_count": "Seleccionadas: {count}",
        "waiting": "Esperando texto nuevo…",
        "scanning": "Leyendo el área seleccionada…",
        "translating": "Traduciendo…",
        "paused": "En pausa mientras la aplicación vinculada está inactiva",
        "no_text": "Aún no hay texto legible",
        "pause": "Pausa",
        "resume": "Continuar",
        "reselect": "Elegir otra área",
        "close": "Detener traducción dinámica",
        "capture_error": "No se puede capturar el área seleccionada",
        "ocr_error": "OCR no está disponible para este modo",
        "translation_error": "Error de traducción; se reintentará",
        "wayland_error": "La captura continua no está disponible mediante el portal Wayland. Usa una sesión X11.",
    },
    "de": {
        "title": "Dynamische Übersetzung",
        "select": "Einen oder mehrere Bereiche zum Ersetzen des Textes auswählen",
        "select_hint": "Alle Bereiche markieren, dann Start oder Enter · Rücktaste entfernt den letzten",
        "start": "Start",
        "undo": "Zurück",
        "selected_count": "Ausgewählt: {count}",
        "waiting": "Warte auf neuen Text…",
        "scanning": "Ausgewählter Bereich wird gelesen…",
        "translating": "Übersetze…",
        "paused": "Pausiert, solange die Ziel-App inaktiv ist",
        "no_text": "Noch kein lesbarer Text",
        "pause": "Pause",
        "resume": "Fortsetzen",
        "reselect": "Anderen Bereich wählen",
        "close": "Dynamische Übersetzung beenden",
        "capture_error": "Der ausgewählte Bereich kann nicht erfasst werden",
        "ocr_error": "OCR ist für diesen Modus nicht verfügbar",
        "translation_error": "Übersetzung fehlgeschlagen; neuer Versuch folgt",
        "wayland_error": "Daueraufnahme ist über das Wayland-Portal nicht verfügbar. Nutze eine X11-Sitzung.",
    },
    "fr": {
        "title": "Traduction dynamique",
        "select": "Sélectionnez une ou plusieurs zones dont le texte doit être remplacé",
        "select_hint": "Tracez toutes les zones puis cliquez sur Démarrer ou Entrée · Retour supprime la dernière",
        "start": "Démarrer",
        "undo": "Annuler",
        "selected_count": "Sélectionnées : {count}",
        "waiting": "En attente d’un nouveau texte…",
        "scanning": "Lecture de la zone sélectionnée…",
        "translating": "Traduction…",
        "paused": "En pause tant que l’application liée est inactive",
        "no_text": "Aucun texte lisible pour l’instant",
        "pause": "Pause",
        "resume": "Reprendre",
        "reselect": "Choisir une autre zone",
        "close": "Arrêter la traduction dynamique",
        "capture_error": "Impossible de capturer la zone sélectionnée",
        "ocr_error": "L’OCR est indisponible pour ce mode",
        "translation_error": "Échec de la traduction ; nouvelle tentative à venir",
        "wayland_error": "La capture continue n’est pas disponible via le portail Wayland. Utilisez une session X11.",
    },
    "zh": {
        "title": "动态翻译",
        "select": "选择一个或多个需要替换文字的区域",
        "select_hint": "画出全部区域，然后点开始或按 Enter · Backspace 删除最后一个",
        "start": "开始",
        "undo": "撤销",
        "selected_count": "已选择：{count}",
        "waiting": "等待新文字…",
        "scanning": "正在读取所选区域…",
        "translating": "正在翻译…",
        "paused": "绑定应用未激活，已暂停",
        "no_text": "暂未发现可读文字",
        "pause": "暂停",
        "resume": "继续",
        "reselect": "重新选择区域",
        "close": "停止动态翻译",
        "capture_error": "无法捕获所选区域",
        "ocr_error": "此模式下 OCR 不可用",
        "translation_error": "翻译失败，稍后将重试",
        "wayland_error": "Wayland 截图门户不支持连续捕获。请使用 X11 会话。",
    },
}


def game_text(language, key):
    texts = GAME_TEXT.get(str(language or "en"), GAME_TEXT["en"])
    return texts.get(key, GAME_TEXT["en"].get(key, key))


def normalize_game_ocr_text(text):
    """Collapse OCR whitespace without erasing punctuation used by dialogue."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def game_texts_are_similar(left, right, threshold=0.90):
    left = normalize_game_ocr_text(left).casefold()
    right = normalize_game_ocr_text(right).casefold()
    if not left or not right:
        return False
    if left == right:
        return True
    return difflib.SequenceMatcher(None, left, right).ratio() >= float(threshold)


def game_frame_fingerprint(image, width=24, height=12):
    """A tiny grayscale frame signature cheap enough to compute every tick."""
    if image is None or image.isNull():
        return ()
    sample = image.scaled(
        width,
        height,
        QtCore.Qt.IgnoreAspectRatio,
        QtCore.Qt.FastTransformation,
    ).convertToFormat(QtGui.QImage.Format_Grayscale8)
    return tuple(QtGui.QColor(sample.pixel(x, y)).red() for y in range(height) for x in range(width))


def game_frames_are_different(previous, current, threshold=4.0):
    if not previous or not current or len(previous) != len(current):
        return True
    difference = sum(abs(a - b) for a, b in zip(previous, current)) / len(current)
    return difference >= float(threshold)


def _foreground_window():
    if not platform_support.IS_WINDOWS:
        return 0
    try:
        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def _window_rect(handle):
    if not platform_support.IS_WINDOWS or not handle:
        return QtCore.QRect()
    try:
        if wintypes is None:
            return QtCore.QRect()
        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(int(handle), ctypes.byref(rect)):
            return QtCore.QRect()
        return QtCore.QRect(
            int(rect.left),
            int(rect.top),
            max(0, int(rect.right - rect.left)),
            max(0, int(rect.bottom - rect.top)),
        )
    except Exception:
        return QtCore.QRect()


def _window_is_minimized(handle):
    if not platform_support.IS_WINDOWS or not handle:
        return False
    try:
        return bool(ctypes.windll.user32.IsIconic(int(handle)))
    except Exception:
        return False


def _window_belongs_to_this_process(handle):
    if not platform_support.IS_WINDOWS or not handle:
        return False
    try:
        process_id = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(
            int(handle), ctypes.byref(process_id)
        )
        return int(process_id.value) == os.getpid()
    except Exception:
        return False


def _exclude_from_windows_capture(widget):
    """Keep our subtitle card out of the frames sent back into OCR."""
    if not platform_support.IS_WINDOWS:
        return False
    try:
        hwnd = int(widget.winId())
        # WDA_EXCLUDEFROMCAPTURE (Windows 10 2004+), with WDA_MONITOR fallback.
        if ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011):
            return True
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000001))
    except Exception:
        return False


def _prepare_game_ocr_variants(qimage):
    """Prepare one low-latency, game-font-friendly OCR image."""
    from PIL import Image, ImageEnhance, ImageOps, ImageStat

    converted = qimage.convertToFormat(QtGui.QImage.Format_RGBA8888)
    pointer = converted.constBits()
    pointer.setsize(converted.byteCount())
    image = Image.frombuffer(
        "RGBA",
        (converted.width(), converted.height()),
        bytes(pointer),
        "raw",
        "RGBA",
        0,
        1,
    ).convert("L")
    image = ImageOps.autocontrast(image, cutoff=1)
    if ImageStat.Stat(image).mean[0] < 128:
        image = ImageOps.invert(image)
    # Pixel dialogue fonts benefit from moderate enlargement, but continuously
    # processing a 4x image is unnecessarily expensive for ordinary subtitles.
    if image.height < 80:
        image = image.resize((image.width * 3, image.height * 3), Image.Resampling.NEAREST)
    elif image.height < 180:
        image = image.resize((image.width * 2, image.height * 2), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.45)
    image = ImageEnhance.Sharpness(image).enhance(1.35)
    border = max(8, min(20, image.height // 14))
    image = ImageOps.expand(image, border=border, fill=255)
    return [("game", image)]


class GameRegionSelector(QtWidgets.QWidget):
    """One-time region and language selector for the continuous session."""

    def __init__(self, target_window=0):
        super().__init__()
        from ocr import (
            _cached_qt_icon,
            _translation_targets_for_source,
            get_cached_ocr_config,
            installed_ocr_language_codes,
        )
        from languages import LANGUAGES, default_target_for_source, language_icon_path

        self._translation_targets_for_source = _translation_targets_for_source
        self._target_window = int(target_window or 0)
        self._start = None
        self._end = None
        self._regions = []
        self._starting_session = False
        self._config = get_cached_ocr_config()
        self._language = str(self._config.get("interface_language", "en"))
        self._available_languages = LANGUAGES
        self._default_target = default_target_for_source
        self._icon = _cached_qt_icon
        self._language_icon_path = language_icon_path

        cursor = QtGui.QCursor.pos()
        self._screen = QtWidgets.QApplication.screenAt(cursor) or QtWidgets.QApplication.primaryScreen()
        self.setGeometry(self._screen.geometry())
        self.setWindowFlags(
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setCursor(QtCore.Qt.CrossCursor)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        self.source_combo = QtWidgets.QComboBox(self)
        self.target_combo = QtWidgets.QComboBox(self)
        self.swap_button = LanguageSwapButton(self)
        self.undo_button = QtWidgets.QPushButton(game_text(self._language, "undo"), self)
        self.start_button = QtWidgets.QPushButton(self)
        available = set(installed_ocr_language_codes(config=self._config))
        if str(self._config.get("translator_engine", "Google")).lower() == "argos":
            available = {
                code for code in available
                if _translation_targets_for_source(code, self._config)
            }
        for language in LANGUAGES:
            if language.code not in available:
                continue
            self.source_combo.addItem(
                _cached_qt_icon(language_icon_path(language.code)),
                language.short_label,
                language.code,
            )
        source = str(
            self._config.get("game_translate_source_language")
            or self._config.get("ocr_translate_source_language")
            or "en"
        )
        source_index = self.source_combo.findData(source)
        self.source_combo.setCurrentIndex(source_index if source_index >= 0 else 0)
        target = str(
            self._config.get("game_translate_target_language")
            or self._config.get("ocr_translate_target_language")
            or default_target_for_source(source)
        )
        self._fill_targets(target)

        combo_qss = """
            QComboBox { background: rgba(20, 23, 30, 248); color: #f7f8fb;
                border: 1px solid rgba(142, 116, 178, 210); border-radius: 11px;
                padding: 6px 9px; font: 700 14px 'Segoe UI'; }
            QComboBox:hover { border-color: #b596dd; background: rgba(31, 35, 45, 252); }
            QComboBox::drop-down { width: 0; border: none; }
            QComboBox::down-arrow { image: none; width: 0; }
            QComboBox QAbstractItemView { background: #15131a; color: #fff;
                border: 1px solid #725b8d; selection-background-color: #5d4777;
                outline: none; padding: 5px; }
            QComboBox QAbstractItemView::item { min-height: 30px; padding: 3px 7px; }
        """
        for combo in (self.source_combo, self.target_combo):
            combo.setStyleSheet(combo_qss)
            combo.setIconSize(QtCore.QSize(28, 28))
            combo.setFixedSize(112, 44)
        self.swap_button.setFixedSize(34, 44)
        self.swap_button.setStyleSheet(
            "QToolButton { color:#c6a4ee; background:rgba(25,22,31,248);"
            " border:1px solid #665276; border-radius:10px; font-size:17px; font-weight:800; }"
            "QToolButton:hover { background:#342b40; border-color:#b596dd; }"
        )
        selector_button_qss = (
            "QPushButton { color:#f8f5fb; background:rgba(25,22,31,248);"
            " border:1px solid #665276; border-radius:10px; padding:0 12px;"
            " font:700 13px 'Segoe UI'; }"
            "QPushButton:hover { background:#342b40; border-color:#b596dd; }"
            "QPushButton:disabled { color:#776e7f; border-color:#44394e; background:rgba(20,18,24,220); }"
        )
        self.undo_button.setStyleSheet(selector_button_qss)
        self.start_button.setStyleSheet(
            selector_button_qss
            + "QPushButton:enabled { background:#76549b; border-color:#b596dd; }"
            + "QPushButton:enabled:hover { background:#8964af; }"
        )
        self.undo_button.setFixedSize(92, 44)
        self.start_button.setFixedSize(142, 44)
        self._layout_controls()
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        self.target_combo.currentIndexChanged.connect(self._persist_pair)
        self.swap_button.clicked.connect(self._swap)
        self.undo_button.clicked.connect(self._undo_last_region)
        self.start_button.clicked.connect(self._start_selected_regions)
        self._update_selection_controls()

        self.show()
        self.raise_()
        self.activateWindow()

    def _layout_controls(self):
        widths = (112, 34, 112, 92, 142)
        gaps = (8, 8, 14, 8)
        total = sum(widths) + sum(gaps)
        x = max(10, (self.width() - total) // 2)
        y = 48
        self.source_combo.move(x, y)
        x += widths[0] + gaps[0]
        self.swap_button.move(x, y)
        x += widths[1] + gaps[1]
        self.target_combo.move(x, y)
        x += widths[2] + gaps[2]
        self.undo_button.move(x, y)
        x += widths[3] + gaps[3]
        self.start_button.move(x, y)

    def _update_selection_controls(self):
        count = len(self._regions)
        self.undo_button.setEnabled(count > 0)
        self.start_button.setEnabled(count > 0)
        label = game_text(self._language, "start")
        if count:
            label = f"{label} ({count})"
        self.start_button.setText(label)
        self.update()

    def _undo_last_region(self):
        if self._regions:
            self._regions.pop()
        self._update_selection_controls()

    def _start_selected_regions(self):
        if not self._regions:
            return
        origin = self.geometry().topLeft()
        global_rects = [QtCore.QRect(rect).translated(origin) for rect in self._regions]
        source = str(self.source_combo.currentData() or "en")
        target = str(self.target_combo.currentData() or "ru")
        target_window = self._target_window
        self._persist_pair()
        self._starting_session = True
        self.close()
        QtCore.QTimer.singleShot(
            80,
            lambda: _begin_game_session(global_rects, source, target, target_window),
        )

    def _fill_targets(self, selected=None):
        source = self.source_combo.currentData()
        targets = set(self._translation_targets_for_source(str(source), self._config))
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        for language in self._available_languages:
            if language.code not in targets:
                continue
            self.target_combo.addItem(
                self._icon(self._language_icon_path(language.code)),
                language.short_label,
                language.code,
            )
        index = self.target_combo.findData(selected)
        if index < 0:
            index = self.target_combo.findData(self._default_target(str(source), selected))
        self.target_combo.setCurrentIndex(index if index >= 0 else 0)
        self.target_combo.blockSignals(False)
        self._persist_pair()

    def _source_changed(self):
        self._fill_targets(self.target_combo.currentData())

    def _persist_pair(self):
        source, target = self.source_combo.currentData(), self.target_combo.currentData()
        if not source or not target or source == target:
            return
        from ocr import _write_ocr_config_updates
        _write_ocr_config_updates({
            "game_translate_source_language": str(source),
            "game_translate_target_language": str(target),
        })

    def _swap(self):
        source, target = self.source_combo.currentData(), self.target_combo.currentData()
        target_index = self.source_combo.findData(target)
        if target_index < 0:
            return
        self.source_combo.blockSignals(True)
        self.source_combo.setCurrentIndex(target_index)
        self.source_combo.blockSignals(False)
        self._fill_targets(source)
        reverse_index = self.target_combo.findData(source)
        if reverse_index >= 0:
            self.target_combo.setCurrentIndex(reverse_index)
        self._persist_pair()

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(4, 7, 12, 112))
        active_rect = (
            QtCore.QRect(self._start, self._end).normalized()
            if self._start is not None and self._end is not None
            else None
        )
        for index, rect in enumerate((*self._regions, active_rect), start=1):
            if rect is None or rect.isNull():
                continue
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QtCore.Qt.transparent)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
            painter.setPen(QtGui.QPen(QtGui.QColor("#b596dd"), 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(rect, 8, 8)
            if rect is not active_rect:
                badge = QtCore.QRect(rect.left() + 7, rect.top() + 7, 28, 24)
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(QtGui.QColor(77, 52, 103, 235))
                painter.drawRoundedRect(badge, 7, 7)
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold))
                painter.drawText(badge, QtCore.Qt.AlignCenter, str(index))

        title_font = QtGui.QFont("Segoe UI", 15, QtGui.QFont.Bold)
        hint_font = QtGui.QFont("Segoe UI", 10)
        painter.setFont(title_font)
        painter.setPen(QtGui.QColor("#ffffff"))
        title_rect = QtCore.QRect(20, 102, self.width() - 40, 30)
        painter.drawText(title_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, game_text(self._language, "select"))
        painter.setFont(hint_font)
        painter.setPen(QtGui.QColor("#d5c6e8"))
        hint_rect = QtCore.QRect(20, 132, self.width() - 40, 26)
        painter.drawText(hint_rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, game_text(self._language, "select_hint"))
        if self._regions:
            count_text = game_text(self._language, "selected_count").format(
                count=len(self._regions)
            )
            painter.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.DemiBold))
            painter.setPen(QtGui.QColor("#ffffff"))
            painter.drawText(
                QtCore.QRect(20, 160, self.width() - 40, 24),
                QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter,
                count_text,
            )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.close()
            return
        if event.button() == QtCore.Qt.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or self._start is None:
            return
        self._end = event.pos()
        local = QtCore.QRect(self._start, self._end).normalized()
        self._start = self._end = None
        if local.width() < 180 or local.height() < 70:
            self.update()
            return
        self._regions.append(local)
        self._update_selection_controls()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
            return
        if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self._start_selected_regions()
            return
        if event.key() in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete):
            self._undo_last_region()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_controls()

    def closeEvent(self, event):
        global _game_selector_ref
        if _game_selector_ref is self:
            _game_selector_ref = None
        if not self._starting_session:
            try:
                from mode_coordinator import release_mode
                release_mode("game")
            except Exception:
                pass
        super().closeEvent(event)
        self.deleteLater()


class GameTranslationOverlay(QtWidgets.QWidget):
    """Click-through live translation painted over the selected source area."""

    translation_ready = QtCore.pyqtSignal(int, str, str, str)

    def __init__(
        self,
        region,
        source_language,
        target_language,
        target_window=0,
        start_delay_ms=0,
    ):
        super().__init__()
        from ocr import get_cached_ocr_config

        self.region = QtCore.QRect(region)
        self.source_language = str(source_language)
        self.target_language = str(target_language)
        self.target_window = int(target_window or 0)
        self.config = get_cached_ocr_config()
        self.language = str(self.config.get("interface_language", "en"))
        self.interval_ms = max(450, min(10000, int(self.config.get("game_capture_interval_ms", 850))))
        self.similarity = max(0.72, min(0.98, float(self.config.get("game_text_similarity", 0.90))))
        self.paused = False
        self._dragging = False
        self._position_locked = True
        self._session_handoff = False
        self._drag_offset = QtCore.QPoint()
        self._ocr_busy = False
        self._translation_busy = False
        self._workers = set()
        self._revision = 0
        self._last_frame = ()
        self._unchanged_ticks = 0
        self._last_source_text = ""
        self._pending_source_text = ""
        self._created_at = time.monotonic()
        self._bound_window_rect = _window_rect(self.target_window)
        self._bound_offset = (
            self.region.topLeft() - self._bound_window_rect.topLeft()
            if not self._bound_window_rect.isNull()
            else QtCore.QPoint()
        )

        flags = (
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        transparent_input = getattr(QtCore.Qt, "WindowTransparentForInput", None)
        if transparent_input is not None:
            flags |= transparent_input
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setWindowIcon(QtGui.QIcon())
        self.setGeometry(self.region)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.card = QtWidgets.QFrame()
        self.card.setObjectName("gameTranslationCard")
        root.addWidget(self.card)
        card_layout = QtWidgets.QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 9, 10, 11)
        card_layout.setSpacing(5)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setObjectName("gameStatusDot")
        self.title_label = QtWidgets.QLabel(game_text(self.language, "title"))
        self.title_label.setObjectName("gameTitle")
        self.pair_label = QtWidgets.QLabel(
            f"{self.source_language.upper()} → {self.target_language.upper()}"
        )
        self.pair_label.setObjectName("gamePair")
        header.addWidget(self.status_dot)
        header.addWidget(self.title_label)
        header.addSpacing(5)
        header.addWidget(self.pair_label)
        header.addStretch()
        self.reselect_button = QtWidgets.QToolButton()
        self.reselect_button.setText("⌖")
        self.reselect_button.setToolTip(game_text(self.language, "reselect"))
        self.pause_button = QtWidgets.QToolButton()
        self.pause_button.setText("Ⅱ")
        self.pause_button.setToolTip(game_text(self.language, "pause"))
        self.close_button = QtWidgets.QToolButton()
        self.close_button.setText("×")
        self.close_button.setToolTip(game_text(self.language, "close"))
        for button in (self.reselect_button, self.pause_button, self.close_button):
            button.setFixedSize(26, 26)
            header.addWidget(button)
        card_layout.addLayout(header)
        # The selected-area workflow replaces the source in place and must not
        # steal mouse input from the game. Ctrl+Alt+G stops it; selecting again
        # starts a fresh region, so no floating toolbar is needed here.
        for widget in (
            self.status_dot,
            self.title_label,
            self.pair_label,
            self.reselect_button,
            self.pause_button,
            self.close_button,
        ):
            widget.hide()

        self.original_label = QtWidgets.QLabel("")
        self.original_label.setObjectName("gameOriginal")
        self.original_label.setWordWrap(True)
        self.original_label.hide()
        card_layout.addWidget(self.original_label)
        self.translation_label = QtWidgets.QLabel(game_text(self.language, "waiting"))
        self.translation_label.setObjectName("gameTranslation")
        self.translation_label.setWordWrap(True)
        self.translation_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        card_layout.addWidget(self.translation_label)
        self.status_label = QtWidgets.QLabel(game_text(self.language, "waiting"))
        self.status_label.setObjectName("gameStatus")
        self.status_label.hide()
        card_layout.addWidget(self.status_label)

        self.reselect_button.clicked.connect(self._reselect)
        self.pause_button.clicked.connect(self._toggle_pause)
        self.close_button.clicked.connect(self.close)
        self.translation_ready.connect(self._apply_translation)
        self._apply_style()
        self._place_near_region()
        # Stay visually transparent until the first useful translation. This
        # avoids a dark rectangle flashing over every selected game area while
        # the initial OCR request is still running.
        self.card.hide()
        self.show()
        self.raise_()
        self._capture_excluded = _exclude_from_windows_capture(self)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._scan_once)
        QtCore.QTimer.singleShot(
            180 + max(0, int(start_delay_ms)), self._start_scanning
        )

    def _start_scanning(self):
        if not self._timer.isActive():
            self._timer.start()
        self._scan_once()

    def _apply_style(self):
        dark = self.config.get("theme", "Темная") == "Темная"
        opacity = max(45, min(100, int(self.config.get("game_overlay_opacity", 88))))
        alpha = round(255 * opacity / 100)
        background = (
            f"rgba(18, 16, 22, {alpha})"
            if dark else f"rgba(235, 230, 239, {alpha})"
        )
        border = "#6b587d" if dark else "#c5b2d7"
        text = "#fbf9fd" if dark else "#251f2b"
        muted = "#a79caf" if dark else "#716879"
        source = "#bba6ce" if dark else "#745b88"
        hover = "#352b40" if dark else "#e9dff0"
        self.setStyleSheet(f"""
            QFrame#gameTranslationCard {{ background: {background}; border: 1px solid {border}; border-radius: 14px; }}
            QLabel {{ background: transparent; border: none; }}
            QLabel#gameStatusDot {{ color: #8fd18b; font-size: 12px; }}
            QLabel#gameTitle {{ color: {text}; font: 800 13px 'Segoe UI'; }}
            QLabel#gamePair {{ color: #b895df; font: 800 12px 'Segoe UI'; }}
            QLabel#gameOriginal {{ color: {source}; font: 600 12px 'Segoe UI'; }}
            QLabel#gameTranslation {{ color: {text}; font: 700 18px 'Segoe UI'; padding: 2px 0; }}
            QLabel#gameStatus {{ color: {muted}; font: 600 11px 'Segoe UI'; }}
            QToolButton {{ color: {text}; background: transparent; border: none; border-radius: 7px; font: 800 16px 'Segoe UI'; }}
            QToolButton:hover {{ background: {hover}; }}
        """)

    def _set_status(self, key, active=True):
        self.status_label.setText(game_text(self.language, key))
        self.status_dot.setStyleSheet(
            "color: #8fd18b;" if active else "color: #a597ac;"
        )
        # Fast-changing Reading/Translating/Waiting captions made a stable
        # subtitle look as if it was flickering. Keep the previous translation
        # untouched; only persistent states need a visible explanation.
        visible = key in {"paused", "capture_error", "ocr_error", "translation_error"}
        self.status_label.setVisible(visible)
        if visible:
            self.card.show()

    def _place_near_region(self):
        # Keep the translated surface exactly on top of the selected source.
        # The old subtitle card sat outside the region, which made this mode a
        # second result window instead of an in-place game translation.
        self.setGeometry(self.region)

    def _update_bound_region(self):
        if not self.target_window or self._bound_window_rect.isNull():
            return
        current = _window_rect(self.target_window)
        if current.isNull():
            return
        new_top_left = current.topLeft() + self._bound_offset
        moved = new_top_left != self.region.topLeft()
        self.region.moveTopLeft(new_top_left)
        if moved:
            self._place_near_region()

    def _target_is_active(self):
        if not bool(self.config.get("game_pause_when_inactive", True)):
            return True
        if not self.target_window or not platform_support.IS_WINDOWS:
            return True
        if _window_is_minimized(self.target_window):
            return False
        # Give focus a moment to return after the region selector closes.
        if time.monotonic() - self._created_at < 1.0:
            return True
        foreground = _foreground_window()
        return foreground in {self.target_window, int(self.winId())}

    def _grab_region(self):
        from ocr import grab_screen_pixmap
        screen = QtWidgets.QApplication.screenAt(self.region.center()) or QtWidgets.QApplication.primaryScreen()
        geometry = screen.geometry()
        local = self.region.translated(-geometry.left(), -geometry.top())
        restore_opacity = False
        if not self._capture_excluded:
            self.setWindowOpacity(0.0)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            restore_opacity = True
        try:
            return grab_screen_pixmap(
                screen, local.x(), local.y(), local.width(), local.height()
            )
        finally:
            if restore_opacity:
                self.setWindowOpacity(1.0)

    def _scan_once(self):
        if self.paused or self._ocr_busy or self._translation_busy:
            return
        try:
            self._update_bound_region()
            if not self._target_is_active():
                self._set_status("paused", active=False)
                return
            pixmap = self._grab_region()
            if pixmap.isNull():
                self._set_status("capture_error", active=False)
                return
            qimage = pixmap.toImage()
            fingerprint = game_frame_fingerprint(qimage)
            if not game_frames_are_different(self._last_frame, fingerprint):
                self._unchanged_ticks += 1
                # A periodic retry recovers from a transient OCR failure without
                # doing expensive recognition work on every identical frame.
                if self._unchanged_ticks < max(2, round(10000 / self.interval_ms)):
                    self._set_status("waiting")
                    return
                self._unchanged_ticks = 0
            else:
                self._unchanged_ticks = 0
            self._last_frame = fingerprint
            self._set_status("scanning")
            self._start_ocr(qimage)
        except Exception:
            self._ocr_busy = False
            logging.getLogger("clickntranslate.game").exception("Game capture/OCR tick failed")
            self._set_status("ocr_error", active=False)

    def _start_ocr(self, qimage):
        from ocr import (
            EasyOCRWorker,
            OCRWorker,
            RapidOCRWorker,
            ScreenCaptureOverlay,
            TesseractOCRWorker,
            _new_ocr_session_id,
            load_image_from_pil,
            usable_ocr_engine,
        )

        variants = _prepare_game_ocr_variants(qimage)
        engine = usable_ocr_engine(self.config.get("ocr_engine", "Windows"))
        session = _new_ocr_session_id("game")
        worker = None
        if engine.lower() == "windows":
            bitmap = load_image_from_pil(variants[0][1])
            if bitmap is not None:
                worker = OCRWorker(
                    bitmap,
                    self.source_language,
                    use_universal=self.source_language in {"auto", "universal"},
                    attempts=[("game", bitmap)],
                    session_id=session,
                )
        elif engine.lower() == "tesseract":
            command = ScreenCaptureOverlay.get_tesseract_cmd()
            if command:
                worker = TesseractOCRWorker(
                    variants,
                    self.source_language,
                    command,
                    "game-continuous",
                    session,
                )
        elif engine.lower() == "rapidocr":
            worker = RapidOCRWorker(variants, "game-continuous", session)
        elif engine.lower() == "easyocr":
            worker = EasyOCRWorker(
                variants,
                self.source_language,
                "game-continuous",
                session,
            )

        if worker is None:
            self._set_status("ocr_error", active=False)
            return
        self._ocr_busy = True
        self._workers.add(worker)
        worker.result_ready.connect(self._on_ocr_result)
        worker.finished.connect(self._ocr_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @QtCore.pyqtSlot(str)
    def _on_ocr_result(self, text):
        normalized = normalize_game_ocr_text(text)
        if not normalized:
            self._set_status("no_text", active=False)
            return
        if game_texts_are_similar(self._last_source_text, normalized, self.similarity):
            self._set_status("waiting")
            return
        self._last_source_text = normalized
        self._start_translation(normalized)

    @QtCore.pyqtSlot()
    def _ocr_finished(self):
        worker = self.sender()
        self._workers.discard(worker)
        self._ocr_busy = False

    def _start_translation(self, source_text):
        if self._translation_busy:
            self._pending_source_text = source_text
            return
        self._translation_busy = True
        self._revision += 1
        revision = self._revision
        self._set_status("translating")

        def work():
            try:
                from translater import translate_text
                translated = translate_text(
                    source_text,
                    self.source_language,
                    self.target_language,
                )
                self.translation_ready.emit(revision, source_text, str(translated or ""), "")
            except Exception as exc:
                logging.getLogger("clickntranslate.game").exception("Game translation failed")
                self.translation_ready.emit(revision, source_text, "", str(exc))

        threading.Thread(
            target=work,
            name="ClicknTranslate-game-translation",
            daemon=True,
        ).start()

    @QtCore.pyqtSlot(int, str, str, str)
    def _apply_translation(self, revision, source_text, translated, error):
        if revision != self._revision:
            return
        self._translation_busy = False
        if error or not translated:
            self._set_status("translation_error", active=False)
        else:
            from ocr import save_translation_history
            self.original_label.setText(source_text)
            self.original_label.setVisible(
                bool(self.config.get("game_show_original_text", False))
            )
            self.translation_label.setText(translated)
            self.card.show()
            self._set_status("waiting")
            if bool(self.config.get("history", False)):
                save_translation_history(source_text, translated, self.target_language)
            self._place_near_region()
        pending = self._pending_source_text
        self._pending_source_text = ""
        if pending and not game_texts_are_similar(source_text, pending, self.similarity):
            self._start_translation(pending)

    def _toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.setText("▶" if self.paused else "Ⅱ")
        self.pause_button.setToolTip(
            game_text(self.language, "resume" if self.paused else "pause")
        )
        self._set_status("paused" if self.paused else "waiting", active=not self.paused)

    def _reselect(self):
        target = self.target_window
        self._session_handoff = True
        self.close()
        QtCore.QTimer.singleShot(100, lambda: _show_game_selector(target))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and event.pos().y() <= 38:
            self._dragging = True
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self._dragging:
                self._position_locked = True
            self._dragging = False
            event.accept()

    def closeEvent(self, event):
        self._timer.stop()
        self._revision += 1
        for worker in list(self._workers):
            try:
                worker.cancel() if hasattr(worker, "cancel") else worker.requestInterruption()
            except Exception:
                pass
            # QThread must stay referenced until run() actually returns. The
            # cancellation flag is cooperative and WinRT/Tesseract may need a
            # moment to leave their current call after the overlay has closed.
            _lingering_workers.add(worker)
            worker.finished.connect(
                lambda completed=worker: _lingering_workers.discard(completed)
            )
        self._workers.clear()
        if self in _game_overlay_refs:
            _game_overlay_refs.remove(self)
        if not self._session_handoff and not _game_overlay_refs:
            try:
                from mode_coordinator import release_mode
                release_mode("game")
            except Exception:
                pass
        super().closeEvent(event)
        self.deleteLater()


def _qimage_to_pil_rgb(image):
    """Make an owned PIL RGB image from a QImage."""
    from PIL import Image

    converted = image.convertToFormat(QtGui.QImage.Format_RGBA8888)
    pointer = converted.constBits()
    pointer.setsize(converted.byteCount())
    return Image.frombuffer(
        "RGBA",
        (converted.width(), converted.height()),
        bytes(pointer),
        "raw",
        "RGBA",
        0,
        1,
    ).convert("RGB")


class GameTesseractPositionWorker(QtCore.QThread):
    """Tesseract fallback that preserves line rectangles for X11/Linux."""

    result_ready = QtCore.pyqtSignal(object)

    def __init__(self, image, language_code, executable, parent=None):
        super().__init__(parent)
        self.image = image.copy()
        self.language_code = str(language_code)
        self.executable = str(executable or "")

    def run(self):
        lines = []
        try:
            if self.isInterruptionRequested() or not self.executable:
                self.result_ready.emit([])
                return
            import pytesseract
            from languages import tesseract_language_code
            from pytesseract import Output

            pytesseract.pytesseract.tesseract_cmd = self.executable
            data = pytesseract.image_to_data(
                _qimage_to_pil_rgb(self.image),
                lang=tesseract_language_code(self.language_code),
                config="--psm 11",
                output_type=Output.DICT,
            )
            grouped = {}
            count = len(data.get("text", ()))
            for index in range(count):
                if self.isInterruptionRequested():
                    return
                text = str(data["text"][index] or "").strip()
                try:
                    confidence = float(data.get("conf", [-1] * count)[index])
                except (TypeError, ValueError):
                    confidence = -1
                if not text or confidence < 15:
                    continue
                key = (
                    data.get("block_num", [0] * count)[index],
                    data.get("par_num", [0] * count)[index],
                    data.get("line_num", [0] * count)[index],
                )
                grouped.setdefault(key, []).append((
                    int(data["left"][index]),
                    int(data["top"][index]),
                    int(data["width"][index]),
                    int(data["height"][index]),
                    text,
                ))
            for words in grouped.values():
                left = min(word[0] for word in words)
                top = min(word[1] for word in words)
                right = max(word[0] + word[2] for word in words)
                bottom = max(word[1] + word[3] for word in words)
                ordered = sorted(words, key=lambda word: word[0])
                lines.append((
                    left,
                    top,
                    right - left,
                    bottom - top,
                    " ".join(word[4] for word in ordered),
                ))
            lines.sort(key=lambda item: (item[1], item[0]))
        except Exception:
            logging.getLogger("clickntranslate.game").exception(
                "Full-screen Tesseract OCR failed"
            )
            lines = []
        if not self.isInterruptionRequested():
            self.result_ready.emit(lines)


def game_overlay_block_geometry(bounds, source_rect, desired_width, desired_height):
    """Fit a live card to its text while tolerating inaccurate OCR bounds.

    Windows OCR occasionally reports a very wide or tall rectangle for only a
    few glyphs (animated subtitles and outlined game fonts trigger this most
    often).  Treating that rectangle as the card's hard minimum made a two-word
    translation turn into a huge empty panel.  The source box may add a little
    coverage, but the measured source/translation text remains authoritative.
    """
    bounds = QtCore.QRectF(bounds).normalized()
    source = QtCore.QRectF(source_rect).normalized()
    width = max(48.0, float(desired_width))
    height = max(28.0, float(desired_height))
    # Let a believable OCR rectangle cover a little more of the source, while
    # capping a bad rectangle relative to the amount of text actually painted.
    source_width_cap = max(width * 1.35, width + 48.0)
    source_height_cap = max(height * 1.35, height + 16.0)
    width = max(width, min(source.width() + 8.0, source_width_cap))
    height = max(height, min(source.height() + 6.0, source_height_cap))
    width = min(width, bounds.width())
    height = min(height, bounds.height())
    left = min(max(source.left() - 4.0, bounds.left()), bounds.right() - width)
    top = min(max(source.top() - 3.0, bounds.top()), bounds.bottom() - height)
    return QtCore.QRectF(left, top, width, height)


class GameFullscreenOverlay(QtWidgets.QWidget):
    """Continuous positional OCR over one monitor with a click-through overlay."""

    translation_ready = QtCore.pyqtSignal(int, object, str, bool)

    def __init__(self, source_language, target_language, target_window=0):
        super().__init__()
        from ocr import get_cached_ocr_config

        self.config = get_cached_ocr_config()
        self.language = str(self.config.get("interface_language", "en"))
        self.source_language = str(source_language or "en")
        self.target_language = str(target_language or "ru")
        self.target_window = int(target_window or 0)
        if _window_belongs_to_this_process(self.target_window):
            self.target_window = 0
        self.interval_ms = max(
            650,
            min(10000, int(self.config.get("game_capture_interval_ms", 850))),
        )
        self.similarity = max(
            0.72,
            min(0.98, float(self.config.get("game_text_similarity", 0.90))),
        )
        self.opacity = max(
            45,
            min(100, int(self.config.get("game_overlay_opacity", 88))),
        )
        self._ocr_busy = False
        self._translation_busy = False
        self._workers = set()
        self._revision = 0
        self._last_frame = ()
        self._unchanged_ticks = 0
        self._last_layout_signature = ()
        self._blocks = []
        self._has_shown_translation = False
        self._status = game_text(self.language, "waiting")
        self._status_is_error = False
        self._ocr_scale_x = 1.0
        self._ocr_scale_y = 1.0
        self.screenshot = QtGui.QPixmap()

        cursor = QtGui.QCursor.pos()
        window_rect = _window_rect(self.target_window)
        anchor = window_rect.center() if not window_rect.isNull() else cursor
        self._screen = (
            QtWidgets.QApplication.screenAt(anchor)
            or QtWidgets.QApplication.primaryScreen()
        )
        self.setGeometry(self._screen.geometry())
        flags = (
            QtCore.Qt.Tool
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        transparent_input = getattr(QtCore.Qt, "WindowTransparentForInput", None)
        if transparent_input is not None:
            flags |= transparent_input
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_NoSystemBackground, True)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setWindowIcon(QtGui.QIcon())
        self.translation_ready.connect(self._apply_translation)

        self.show()
        self.raise_()
        self._capture_excluded = _exclude_from_windows_capture(self)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self._scan_once)
        self._timer.start()
        QtCore.QTimer.singleShot(220, self._scan_once)

    def _target_is_active(self):
        if not bool(self.config.get("game_pause_when_inactive", True)):
            return True
        if not self.target_window or not platform_support.IS_WINDOWS:
            return True
        if _window_is_minimized(self.target_window):
            return False
        return _foreground_window() == self.target_window

    def _set_status(self, key, error=False):
        # Normal scan phases can change several times per second. Painting all
        # of them made the empty full-screen overlay flash. Once translations
        # exist, keep them stable and repaint only for results or real states.
        if key in {"scanning", "translating", "waiting", "no_text"}:
            if not self._blocks and not self._status:
                self._status = game_text(self.language, "waiting")
            self._status_is_error = False
            return
        self._status = game_text(self.language, key)
        self._status_is_error = bool(error)
        self.update()

    def _grab_screen(self):
        from ocr import grab_screen_pixmap

        geometry = self._screen.geometry()
        restore_opacity = False
        if not self._capture_excluded:
            # Display affinity is unavailable on older Windows and X11. Hide
            # only for the capture call so our own translations never feed
            # back into OCR and multiply on the next frame.
            self.setWindowOpacity(0.0)
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
            restore_opacity = True
        try:
            return grab_screen_pixmap(
                self._screen, 0, 0, geometry.width(), geometry.height()
            )
        finally:
            if restore_opacity:
                self.setWindowOpacity(1.0)

    def _scan_once(self):
        if self._ocr_busy or self._translation_busy:
            return
        if not self._target_is_active():
            self._set_status("paused")
            return
        pixmap = self._grab_screen()
        if pixmap.isNull():
            self._set_status("capture_error", error=True)
            return
        # Keep the newest live frame for the ordinary full-screen replacement
        # renderer, which samples the source background around every OCR line.
        self.screenshot = pixmap
        geometry = self._screen.geometry()
        self._ocr_scale_x = pixmap.width() / max(1, geometry.width())
        self._ocr_scale_y = pixmap.height() / max(1, geometry.height())
        image = pixmap.toImage()
        fingerprint = game_frame_fingerprint(image, width=36, height=20)
        if not game_frames_are_different(self._last_frame, fingerprint, threshold=3.0):
            self._unchanged_ticks += 1
            # Re-read an unchanged screen periodically. This is essential when
            # the previous online request was rate-limited: a static dialogue
            # must recover without the player having to move the camera.
            if self._unchanged_ticks < max(1, round(10000 / self.interval_ms)):
                self._set_status("waiting")
                return
            self._unchanged_ticks = 0
        else:
            self._unchanged_ticks = 0
        self._last_frame = fingerprint
        self._set_status("scanning")
        self._start_position_ocr(image)

    def _start_position_ocr(self, image):
        from ocr import (
            FullScreenOCRWorker,
            ScreenCaptureOverlay,
            qimage_to_softwarebitmap,
        )

        worker = None
        if platform_support.supports_windows_ocr():
            bitmap = qimage_to_softwarebitmap(image)
            if bitmap is not None:
                worker = FullScreenOCRWorker(bitmap, self.source_language)
        else:
            command = ScreenCaptureOverlay.get_tesseract_cmd()
            if command:
                worker = GameTesseractPositionWorker(
                    image, self.source_language, command
                )
        if worker is None:
            self._set_status("ocr_error", error=True)
            return
        self._ocr_busy = True
        self._workers.add(worker)
        worker.result_ready.connect(self._on_position_ocr_result)
        worker.finished.connect(self._position_ocr_finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @QtCore.pyqtSlot(object)
    def _on_position_ocr_result(self, lines):
        from ocr import _group_screen_ocr_lines

        grouped = _group_screen_ocr_lines(lines)
        grouped = [
            item for item in grouped
            if len(normalize_game_ocr_text(item[4])) >= 2
        ]
        if not grouped:
            if self._blocks:
                self._blocks = []
                self._last_layout_signature = ()
                self.update()
            self._set_status("no_text")
            return
        signature = tuple(
            (
                round(float(item[0]) / 8),
                round(float(item[1]) / 8),
                normalize_game_ocr_text(item[4]).casefold(),
            )
            for item in grouped
        )
        if signature == self._last_layout_signature:
            self._set_status("waiting")
            return
        self._last_layout_signature = signature
        if self._blocks:
            self._blocks = []
            self.update()
        self._start_block_translation(grouped)

    @QtCore.pyqtSlot()
    def _position_ocr_finished(self):
        worker = self.sender()
        self._workers.discard(worker)
        self._ocr_busy = False

    def _start_block_translation(self, lines):
        self._translation_busy = True
        self._revision += 1
        revision = self._revision
        self._set_status("translating")

        def work():
            error = ""
            try:
                from ocr import _translate_screen_texts
                from translater import translate_text

                ordered_texts = [normalize_game_ocr_text(item[4]) for item in lines]
                translated_values = _translate_screen_texts(
                    ordered_texts,
                    translate_text,
                    self.source_language,
                    self.target_language,
                )
                blocks = []
                for item, source_text, translated in zip(
                    lines, ordered_texts, translated_values
                ):
                    translated = str(translated or "").strip() or source_text
                    blocks.append((
                        float(item[0]),
                        float(item[1]),
                        float(item[2]),
                        float(item[3]),
                        source_text,
                        translated,
                    ))
                # Publish a coherent translated screen in one update. Partial
                # batches made labels from different moments appear together.
                self.translation_ready.emit(revision, blocks, "", True)
            except Exception as exc:
                logging.getLogger("clickntranslate.game").exception(
                    "Full-screen game translation failed"
                )
                error = str(exc)
            if error:
                self.translation_ready.emit(revision, [], error, True)

        threading.Thread(
            target=work,
            name="ClicknTranslate-game-fullscreen-translation",
            daemon=True,
        ).start()

    @QtCore.pyqtSlot(int, object, str, bool)
    def _apply_translation(self, revision, blocks, error, final=True):
        if revision != self._revision:
            return
        self._translation_busy = not bool(final)
        if error:
            self._last_layout_signature = ()
            self._set_status("translation_error", error=True)
            return
        if blocks:
            self._blocks = list(blocks)
            self._has_shown_translation = True
            self._status_is_error = False
            self.update()
        elif final:
            self._last_layout_signature = ()
            self._set_status("translation_error", error=True)
            return
        self._set_status("waiting")
        if final and bool(self.config.get("history", False)):
            from ocr import save_translation_history
            source = "\n".join(block[4] for block in self._blocks)
            translated = "\n".join(block[5] for block in self._blocks)
            save_translation_history(source, translated, self.target_language)

    def paintEvent(self, _event):
        from ocr import FullScreenTranslateOverlay

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        rendered_blocks = []
        source_rects = []
        for x, y, width, height, source, translated in self._blocks:
            source_rect = QtCore.QRectF(
                x / self._ocr_scale_x,
                y / self._ocr_scale_y,
                width / self._ocr_scale_x,
                height / self._ocr_scale_y,
            )
            source_rects.append(source_rect)
            rendered_blocks.append((source_rect, source, translated))

        occupied = []
        painted_blocks = []
        for block_index, (source_rect, source, translated) in enumerate(rendered_blocks):
            layout = FullScreenTranslateOverlay._translation_block_layout(
                self,
                source_rect,
                source,
                translated,
                occupied=occupied,
                obstacles=[
                    obstacle
                    for obstacle_index, obstacle in enumerate(source_rects)
                    if obstacle_index != block_index
                ],
            )
            occupied.append(layout[0])
            painted_blocks.append((source_rect, source, translated, layout))

        # Exactly the same two-pass in-place renderer as ordinary full-screen
        # translation: local replacement backgrounds first, then every line.
        for source_rect, source, translated, layout in painted_blocks:
            FullScreenTranslateOverlay._paint_block(
                self,
                painter,
                source_rect,
                source,
                translated,
                layout=layout,
                draw_text=False,
            )
        for source_rect, source, translated, layout in painted_blocks:
            FullScreenTranslateOverlay._paint_block(
                self,
                painter,
                source_rect,
                source,
                translated,
                layout=layout,
                draw_background=False,
            )

        # No toolbar or second title-bar button is added. A compact passive
        # status only appears until the first translated frame or on errors.
        if (
            (not self._blocks and not self._has_shown_translation)
            or self._status_is_error
        ):
            status_font = QtGui.QFont("Segoe UI", 10, QtGui.QFont.DemiBold)
            painter.setFont(status_font)
            metrics = QtGui.QFontMetrics(status_font)
            width = min(self.width() - 24, metrics.horizontalAdvance(self._status) + 24)
            status_rect = QtCore.QRectF(self.width() - width - 12, 12, width, 30)
            painter.setPen(QtGui.QPen(QtGui.QColor(126, 103, 153, 210), 1))
            painter.setBrush(
                QtGui.QColor(74, 25, 31, 232)
                if self._status_is_error
                else QtGui.QColor(14, 15, 21, 224)
            )
            painter.drawRoundedRect(status_rect, 9, 9)
            painter.setPen(QtGui.QColor(245, 240, 250))
            painter.drawText(status_rect, QtCore.Qt.AlignCenter, self._status)
        painter.end()

    def _replacement_palette(self, rect_f):
        """Use full-screen replacement colours with the Gaming opacity."""
        from ocr import FullScreenTranslateOverlay

        background, foreground = FullScreenTranslateOverlay._replacement_palette(
            self, rect_f
        )
        background.setAlpha(round(255 * self.opacity / 100))
        return background, foreground

    def closeEvent(self, event):
        global _game_fullscreen_ref
        self._timer.stop()
        self._revision += 1
        for worker in list(self._workers):
            try:
                worker.requestInterruption()
            except RuntimeError:
                pass
            _lingering_workers.add(worker)
            worker.finished.connect(
                lambda completed=worker: _lingering_workers.discard(completed)
            )
        self._workers.clear()
        if _game_fullscreen_ref is self:
            _game_fullscreen_ref = None
        super().closeEvent(event)
        self.deleteLater()


_game_selector_ref = None
_game_overlay_refs = []
_game_fullscreen_ref = None
_lingering_workers = set()


def _show_game_selector(target_window=0):
    global _game_selector_ref
    if _game_selector_ref is not None:
        try:
            _game_selector_ref.close()
        except RuntimeError:
            pass
    _game_selector_ref = GameRegionSelector(target_window)
    return _game_selector_ref


def _begin_game_session(regions, source_language, target_language, target_window=0):
    global _game_overlay_refs
    for overlay in list(_game_overlay_refs):
        try:
            overlay.close()
        except RuntimeError:
            pass
    _game_overlay_refs = []
    if isinstance(regions, QtCore.QRect):
        regions = [regions]
    for index, region in enumerate(regions or ()):
        if not isinstance(region, QtCore.QRect) or region.isNull():
            continue
        overlay = GameTranslationOverlay(
            region,
            source_language,
            target_language,
            target_window,
            start_delay_ms=index * 160,
        )
        _game_overlay_refs.append(overlay)
    if not _game_overlay_refs:
        try:
            from mode_coordinator import release_mode
            release_mode("game")
        except Exception:
            pass
    return tuple(_game_overlay_refs)


def _begin_fullscreen_game_session(source_language, target_language, target_window=0):
    global _game_fullscreen_ref
    if _game_fullscreen_ref is not None:
        try:
            _game_fullscreen_ref.close()
        except RuntimeError:
            pass
    _game_fullscreen_ref = GameFullscreenOverlay(
        source_language,
        target_language,
        target_window,
    )
    return _game_fullscreen_ref


def game_mode_active():
    widgets = (_game_selector_ref, *_game_overlay_refs)
    for widget in widgets:
        try:
            if widget is not None and widget.isVisible():
                return True
        except RuntimeError:
            continue
    return False


def stop_game_mode():
    global _game_selector_ref, _game_overlay_refs, _game_fullscreen_ref
    widgets = (_game_selector_ref, _game_fullscreen_ref, *_game_overlay_refs)
    for widget in widgets:
        if widget is None:
            continue
        try:
            widget.close()
        except RuntimeError:
            pass
    _game_selector_ref = None
    _game_overlay_refs = []
    _game_fullscreen_ref = None
    try:
        from mode_coordinator import release_mode
        release_mode("game")
    except Exception:
        pass


def toggle_game_mode():
    """Toggle the single supported Dynamic workflow: selected live areas."""
    from mode_coordinator import release_mode, request_mode

    if not request_mode("game", stop_game_mode):
        return None
    if platform_support.IS_LINUX and platform_support.is_wayland():
        from ocr import get_cached_ocr_config
        language = get_cached_ocr_config().get("interface_language", "en")
        QtWidgets.QMessageBox.information(
            None,
            game_text(language, "title"),
            game_text(language, "wayland_error"),
        )
        release_mode("game")
        return None
    target_window = _foreground_window()
    if _window_belongs_to_this_process(target_window):
        target_window = 0
    return _show_game_selector(target_window)
