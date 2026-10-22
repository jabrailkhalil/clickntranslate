"""Application-language labels for shared dialog actions, independent of OS locale."""
import sys

from PyQt5.QtWidgets import QApplication


LANGUAGES = ('en', 'ru', 'es', 'de', 'fr', 'zh', 'pt', 'it')
_ACTIONS = {
    'Swap languages': ('Swap languages', 'Поменять языки', 'Intercambiar idiomas', 'Sprachen tauschen',
                       'Inverser les langues', '交换语言', 'Trocar idiomas', 'Scambia lingue'),
    'OK': ('OK', 'ОК', 'Aceptar', 'OK', 'OK', '确定', 'OK', 'OK'),
    'Save': ('Save', 'Сохранить', 'Guardar', 'Speichern', 'Enregistrer', '保存', 'Salvar', 'Salva'),
    'Save all': ('Save all', 'Сохранить всё', 'Guardar todo', 'Alles speichern', 'Tout enregistrer', '全部保存', 'Salvar tudo', 'Salva tutto'),
    'Open': ('Open', 'Открыть', 'Abrir', 'Öffnen', 'Ouvrir', '打开', 'Abrir', 'Apri'),
    'Yes': ('Yes', 'Да', 'Sí', 'Ja', 'Oui', '是', 'Sim', 'Sì'),
    'Yes to all': ('Yes to all', 'Да для всех', 'Sí a todo', 'Ja, alle', 'Oui pour tout', '全部是', 'Sim para todos', 'Sì a tutti'),
    'No': ('No', 'Нет', 'No', 'Nein', 'Non', '否', 'Não', 'No'),
    'No to all': ('No to all', 'Нет для всех', 'No a todo', 'Nein, keine', 'Non pour tout', '全部否', 'Não para todos', 'No a tutti'),
    'Abort': ('Abort', 'Прервать', 'Interrumpir', 'Abbrechen', 'Interrompre', '中止', 'Interromper', 'Interrompi'),
    'Retry': ('Retry', 'Повторить', 'Reintentar', 'Erneut versuchen', 'Réessayer', '重试', 'Tentar novamente', 'Riprova'),
    'Ignore': ('Ignore', 'Пропустить', 'Ignorar', 'Ignorieren', 'Ignorer', '忽略', 'Ignorar', 'Ignora'),
    'Close': ('Close', 'Закрыть', 'Cerrar', 'Schließen', 'Fermer', '关闭', 'Fechar', 'Chiudi'),
    'Cancel': ('Cancel', 'Отмена', 'Cancelar', 'Abbrechen', 'Annuler', '取消', 'Cancelar', 'Annulla'),
    'Discard': ('Discard', 'Не сохранять', 'Descartar', 'Verwerfen', 'Ne pas enregistrer', '不保存', 'Descartar', 'Non salvare'),
    'Help': ('Help', 'Справка', 'Ayuda', 'Hilfe', 'Aide', '帮助', 'Ajuda', 'Aiuto'),
    'Apply': ('Apply', 'Применить', 'Aplicar', 'Anwenden', 'Appliquer', '应用', 'Aplicar', 'Applica'),
    'Reset': ('Reset', 'Сбросить', 'Restablecer', 'Zurücksetzen', 'Réinitialiser', '重置', 'Redefinir', 'Ripristina'),
    'Restore defaults': ('Restore defaults', 'Восстановить по умолчанию', 'Restaurar valores predeterminados',
                         'Standardeinstellungen wiederherstellen', 'Rétablir les valeurs par défaut', '恢复默认设置', 'Restaurar padrões', 'Ripristina le impostazioni predefinite'),
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
