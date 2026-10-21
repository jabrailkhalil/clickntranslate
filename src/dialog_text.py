"""Application-language labels for shared dialog actions, independent of OS locale."""
import sys

from PyQt5.QtWidgets import QApplication


LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh')
_ACTIONS = {
    'OK': ('OK', 'ОК', 'Aceptar', 'OK', 'OK', '确定'),
    'Save': ('Save', 'Сохранить', 'Guardar', 'Speichern', 'Enregistrer', '保存'),
    'Save all': ('Save all', 'Сохранить всё', 'Guardar todo', 'Alles speichern', 'Tout enregistrer', '全部保存'),
    'Open': ('Open', 'Открыть', 'Abrir', 'Öffnen', 'Ouvrir', '打开'),
    'Yes': ('Yes', 'Да', 'Sí', 'Ja', 'Oui', '是'),
    'Yes to all': ('Yes to all', 'Да для всех', 'Sí a todo', 'Ja, alle', 'Oui pour tout', '全部是'),
    'No': ('No', 'Нет', 'No', 'Nein', 'Non', '否'),
    'No to all': ('No to all', 'Нет для всех', 'No a todo', 'Nein, keine', 'Non pour tout', '全部否'),
    'Abort': ('Abort', 'Прервать', 'Interrumpir', 'Abbrechen', 'Interrompre', '中止'),
    'Retry': ('Retry', 'Повторить', 'Reintentar', 'Erneut versuchen', 'Réessayer', '重试'),
    'Ignore': ('Ignore', 'Пропустить', 'Ignorar', 'Ignorieren', 'Ignorer', '忽略'),
    'Close': ('Close', 'Закрыть', 'Cerrar', 'Schließen', 'Fermer', '关闭'),
    'Cancel': ('Cancel', 'Отмена', 'Cancelar', 'Abbrechen', 'Annuler', '取消'),
    'Discard': ('Discard', 'Не сохранять', 'Descartar', 'Verwerfen', 'Ne pas enregistrer', '不保存'),
    'Help': ('Help', 'Справка', 'Ayuda', 'Hilfe', 'Aide', '帮助'),
    'Apply': ('Apply', 'Применить', 'Aplicar', 'Anwenden', 'Appliquer', '应用'),
    'Reset': ('Reset', 'Сбросить', 'Restablecer', 'Zurücksetzen', 'Réinitialiser', '重置'),
    'Restore defaults': ('Restore defaults', 'Восстановить по умолчанию', 'Restaurar valores predeterminados',
                         'Standardeinstellungen wiederherstellen', 'Rétablir les valeurs par défaut', '恢复默认设置'),
}


def dialog_language(widget=None):
    """Prefer the nearest explicit app language, including capture-process owners."""
    pending = [widget]
    seen = set()
    app = QApplication.instance()
    if app is not None:
        pending.append(app.activeWindow())
    for name in ('main', '__main__'):
        pending.append(getattr(sys.modules.get(name), '_main_window_ref', None))
    while pending:
        current = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        try:
            for attribute in ('_dialog_language_code', 'current_interface_language',
                              'interface_language', 'language', 'lang'):
                language = getattr(current, attribute, None)
                if isinstance(language, str) and language in LANGUAGES:
                    return language
            config = getattr(current, 'config', None)
            if isinstance(config, dict) and config.get('interface_language') in LANGUAGES:
                return config['interface_language']
            owner = getattr(current, 'owner', None)
            parent = getattr(current, 'parent', None)
            pending[0:0] = [owner, parent() if callable(parent) else parent]
        except (RuntimeError, TypeError):
            continue  # An owner may have been disposed before its modal child.
    return 'en'


def dialog_action_text(widget, action):
    labels = _ACTIONS.get(action)
    return labels[LANGUAGES.index(dialog_language(widget))] if labels is not None else action
