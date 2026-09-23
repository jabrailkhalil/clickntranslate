"""Saved source/output layouts, independent of a running translation session."""

import json
import math
from pathlib import Path

from PyQt5 import QtCore


_COPY = {
    'help': ('How it works', 'Как пользоваться', 'Cómo funciona', 'So funktioniert es', 'Mode d’emploi', '使用方法'),
    'shortcuts': ('Change shortcut', 'Изменить горячую клавишу', 'Cambiar atajo', 'Tastenkürzel ändern', 'Modifier le raccourci', '修改快捷键'),
    'instructions': (
        '1. Choose the source and translation languages.\n2. Drag a rectangle around the text to watch (purple).\n3. Drag a second rectangle where its translation should appear (green). It may be on another monitor.\n4. Click Start. Changed text is translated automatically.\n\nWindow settings beside the output control its text size, background and position. Save a named template to reuse the layout.\n\nEsc cancels selection. Stop beside the output or {hotkey} ends the session.',
        '1. Выберите язык исходника и перевода.\n2. Зажмите левую кнопку и обведите текст, за которым нужно следить (фиолетовая рамка).\n3. Обведите вторую область — где показывать перевод (зелёная рамка). Можно на другом мониторе.\n4. Нажмите «Запустить». При изменении текста перевод обновляется сам.\n\nКнопка «Настройки окна» возле перевода меняет размер текста, фон и положение. Расположение можно сохранить под именем и затем выбрать из шаблонов.\n\nEsc отменяет выбор. Кнопка «Стоп» возле перевода или {hotkey} завершает сеанс.',
        '1. Elige los idiomas.\n2. Arrastra un rectángulo sobre el texto original (morado).\n3. Dibuja otro para la traducción (verde), incluso en otro monitor.\n4. Pulsa Iniciar: el texto se traduce cuando cambia.\n\nLos ajustes junto a la salida cambian texto, fondo y posición. Guarda un nombre para reutilizar la plantilla.\n\nEsc cancela la selección. Detener o {hotkey} finaliza la sesión.',
        '1. Sprachen auswählen.\n2. Den Quelltext mit gedrückter Maustaste umrahmen (violett).\n3. Den Ausgabebereich markieren (grün), auch auf einem anderen Monitor.\n4. Start drücken: Änderungen werden automatisch übersetzt.\n\nDie Fenstereinstellungen neben der Ausgabe ändern Textgröße, Hintergrund und Position. Die Anordnung kann als benannte Vorlage gespeichert werden.\n\nEsc bricht die Auswahl ab. Beenden oder {hotkey} beendet die Sitzung.',
        '1. Choisissez les langues.\n2. Tracez un rectangle autour du texte source (violet).\n3. Tracez la zone de traduction (verte), éventuellement sur un autre écran.\n4. Démarrez : le texte modifié est traduit automatiquement.\n\nLes réglages près de la sortie ajustent le texte, le fond et la position. Enregistrez un modèle nommé pour le réutiliser.\n\nÉchap annule la sélection. Arrêter ou {hotkey} termine la session.',
        '1. 选择原文和译文语言。\n2. 按住左键框选原文（紫色）。\n3. 再框选译文显示区域（绿色），也可在另一台显示器上。\n4. 点击开始，文字变化时自动更新翻译。\n\n译文旁的窗口设置可调整字号、背景和位置。输入名称保存模板，以后可以重新使用。\n\nEsc 取消选择；停止按钮或 {hotkey} 结束会话。'),
    'selection_hint': ('Drag with the left mouse button · Esc cancels', 'Зажмите левую кнопку и протяните рамку · Esc — отмена', 'Arrastra con el botón izquierdo · Esc cancela', 'Mit linker Maustaste ziehen · Esc bricht ab', 'Tracez avec le bouton gauche · Échap annule', '按住左键拖动框选 · Esc 取消'),
    'source': ('1 · Select text to read', '1 · Выделите исходный текст', '1 · Selecciona el texto original', '1 · Quelltext auswählen', '1 · Sélectionnez le texte source', '1 · 选择原文区域'),
    'output': ('2 · Select where to show translation', '2 · Выделите место для перевода', '2 · Selecciona dónde mostrar la traducción', '2 · Bereich für die Übersetzung wählen', '2 · Choisissez où afficher la traduction', '2 · 选择译文显示区域'),
    'ready': ('Add another pair or press Start', 'Можно добавить пару или нажать «Запустить»', 'Añade otra pareja o pulsa Iniciar', 'Weiteres Paar wählen oder Start drücken', 'Ajoutez une paire ou démarrez', '添加另一组区域或点击开始'),
    'read': ('Read', 'Читать', 'Leer', 'Lesen', 'Lire', '原文'),
    'write': ('Translation', 'Перевод', 'Traducción', 'Übersetzung', 'Traduction', '译文'),
    'templates': ('Template name', 'Имя шаблона', 'Nombre de plantilla', 'Vorlagenname', 'Nom du modèle', '模板名称'),
    'save': ('Save template', 'Сохранить шаблон', 'Guardar plantilla', 'Vorlage speichern', 'Enregistrer le modèle', '保存模板'),
    'delete': ('Delete template', 'Удалить шаблон', 'Eliminar plantilla', 'Vorlage löschen', 'Supprimer le modèle', '删除模板'),
    'saved': ('Saved', 'Сохранено', 'Guardado', 'Gespeichert', 'Enregistré', '已保存'),
    'name_required': ('Enter a template name', 'Введите имя шаблона', 'Escribe un nombre', 'Vorlagennamen eingeben', 'Saisissez un nom', '请输入模板名称'),
    'settings': ('Window settings', 'Настройки окна', 'Ajustes de ventana', 'Fenstereinstellungen', 'Réglages de fenêtre', '窗口设置'),
    'font': ('Text size', 'Размер текста', 'Tamaño de texto', 'Schriftgröße', 'Taille du texte', '文字大小'),
    'opacity': ('Background', 'Фон', 'Fondo', 'Hintergrund', 'Fond', '背景'),
    'locked': ('Lock position', 'Закрепить', 'Fijar posición', 'Position sperren', 'Verrouiller', '固定位置'),
    'move': ('Drag to move the output', 'Перетащите, чтобы переместить вывод', 'Arrastra para mover la salida', 'Ziehen zum Verschieben', 'Glissez pour déplacer la sortie', '拖动以移动译文区域'),
    'resize': ('Drag to resize the output', 'Перетащите, чтобы изменить размер', 'Arrastra para cambiar el tamaño', 'Ziehen zum Ändern der Größe', 'Glissez pour redimensionner', '拖动以调整大小'),
    'unavailable': ('Template languages are unavailable', 'Языки шаблона недоступны', 'Idiomas de plantilla no disponibles', 'Vorlagensprachen nicht verfügbar', 'Langues du modèle indisponibles', '模板语言不可用'),
    'save_error': ('Template could not be saved', 'Не удалось сохранить шаблон', 'No se pudo guardar', 'Speichern fehlgeschlagen', 'Enregistrement impossible', '无法保存模板'),
}


def text(language, key):
    languages = ('en', 'ru', 'es', 'de', 'fr', 'zh')
    return _COPY[key][languages.index(language) if language in languages else 0]


def output_style(value=None, *, opacity=88):
    value = value if isinstance(value, dict) else {}
    def number(key, default, low, high):
        try:
            return max(low, min(high, int(value.get(key, default))))
        except (ValueError, TypeError, OverflowError):
            return default
    return {'font_size': number('font_size', 18, 10, 48),
            'opacity': number('opacity', opacity, 0, 100),
            'locked': value.get('locked', True) is not False}


def encode_rect(rect, screens):
    screen = next((screen for screen in screens if screen.geometry().contains(rect.center())), screens[0])
    bounds = screen.geometry()
    rect = rect.intersected(bounds)
    if rect.isEmpty():
        raise ValueError('Region is outside its screen')
    return {'screen': screen.name(), 'rect': [(rect.x()-bounds.x())/bounds.width(),
            (rect.y()-bounds.y())/bounds.height(), rect.width()/bounds.width(), rect.height()/bounds.height()]}


def decode_rect(value, screens):
    screen = next((screen for screen in screens if screen.name() == value['screen']), screens[0])
    bounds = screen.geometry()
    x, y, width, height = value['rect']
    width, height = min(bounds.width(), max(60, round(width*bounds.width()))), min(bounds.height(), max(24, round(height*bounds.height())))
    x = min(max(0, round(x*bounds.width())), bounds.width()-width)
    y = min(max(0, round(y*bounds.height())), bounds.height()-height)
    return QtCore.QRect(bounds.x()+x, bounds.y()+y, width, height)


def validate_template(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid template')
    name = str(value.get('name', '')).strip()[:80]
    source, target = value.get('source_language'), value.get('target_language')
    pairs = value.get('pairs')
    if not name or not all(isinstance(code, str) and 1 <= len(code) <= 20 for code in (source, target)):
        raise ValueError('Invalid template name or languages')
    if not isinstance(pairs, list) or not 1 <= len(pairs) <= 16:
        raise ValueError('Invalid template regions')
    clean = []
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError('Invalid template pair')
        item = {}
        for key in ('source', 'output'):
            area = pair.get(key, {})
            if not isinstance(area, dict):
                raise ValueError('Invalid template region')
            rect = area.get('rect')
            if (not isinstance(rect, list) or len(rect) != 4
                    or not all(isinstance(n, (int, float)) and not isinstance(n, bool) and 0 <= n <= 1 and math.isfinite(n) for n in rect)
                    or rect[2] <= 0 or rect[3] <= 0 or rect[0]+rect[2] > 1.000001 or rect[1]+rect[3] > 1.000001):
                raise ValueError('Invalid template coordinates')
            item[key] = {'screen': str(area.get('screen', ''))[:200], 'rect': list(rect)}
        item['style'] = output_style(pair.get('style'))
        clean.append(item)
    return {'name': name, 'source_language': source, 'target_language': target, 'pairs': clean}


class TemplateStore:
    def __init__(self, path=None):
        if path is None:
            from ocr import get_data_file
            path = get_data_file('dynamic_templates.json')
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('templates'), list):
            raise ValueError('Unsupported templates file')
        return [validate_template(value) for value in data['templates'][:100]]

    def _write(self, values):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        output = QtCore.QSaveFile(str(self.path))
        if not output.open(QtCore.QIODevice.WriteOnly):
            raise OSError(output.errorString())
        data = json.dumps({'version': 1, 'templates': values}, ensure_ascii=False, indent=2).encode('utf-8')
        if output.write(data) != len(data) or not output.commit():
            raise OSError(output.errorString())

    def save(self, value):
        value = validate_template(value)
        values = [item for item in self.load() if item['name'].casefold() != value['name'].casefold()]
        if len(values) >= 100:
            raise ValueError('Too many templates')
        self._write(values + [value])
        return value

    def delete(self, name):
        self._write([item for item in self.load() if item['name'] != name])
