"""Fast offline-provider checks and an actionable, localized recovery prompt."""
from dataclasses import dataclass


_TEXT = {
    'en': ('Offline translation is not ready', 'The Argos package for {pair} is not installed.',
           'The Hy-MT model or its local runner is missing.', 'Open installation',
           'Available translators', 'Use selected', 'Online · internet required', 'Offline'),
    'ru': ('Офлайн-перевод не настроен', 'Не установлен пакет Argos для направления «{pair}».',
           'Не найдена модель Hy-MT или программа для её запуска.', 'Перейти к установке',
           'Доступные переводчики', 'Использовать выбранный', 'Онлайн · нужен интернет', 'Офлайн'),
    'es': ('La traducción sin conexión no está lista', 'Falta el paquete Argos para {pair}.',
           'Falta el modelo Hy-MT o su motor local.', 'Abrir instalación',
           'Traductores disponibles', 'Usar seleccionado', 'En línea · requiere internet', 'Sin conexión'),
    'de': ('Offline-Übersetzung ist nicht eingerichtet', 'Das Argos-Sprachpaket für {pair} fehlt.',
           'Das Hy-MT-Modell oder seine lokale Laufzeit fehlt.', 'Installation öffnen',
           'Verfügbare Übersetzer', 'Auswahl verwenden', 'Online · Internet erforderlich', 'Offline'),
    'fr': ('La traduction hors ligne n’est pas configurée', 'Le module Argos pour {pair} manque.',
           'Le modèle Hy-MT ou son moteur local manque.', 'Ouvrir l’installation',
           'Traducteurs disponibles', 'Utiliser la sélection', 'En ligne · connexion requise', 'Hors ligne'),
    'zh': ('离线翻译尚未就绪', '尚未安装 {pair} 的 Argos 语言包。',
           '缺少 Hy-MT 模型或本地运行程序。', '打开安装页面',
           '可用翻译引擎', '使用所选引擎', '在线 · 需要网络', '离线'),

    'pt': ('A tradução offline não está pronta',
     'O pacote Argos para {pair} não está instalado.',
     'O modelo Hy-MT ou seu executável local não foi encontrado.',
     'Abrir instalação',
     'Tradutores disponíveis',
     'Usar selecionado',
     'On-line · internet necessária',
     'Offline'),
    'it': ('La traduzione offline non è pronta',
     'Il pacchetto Argos per {pair} non è installato.',
     'Il modello Hy-MT o il suo eseguibile locale non è presente.',
     'Apri installazione',
     'Traduttori disponibili',
     'Usa selezionato',
     'Online · Internet richiesto',
     'Offline'),
}
_KEYS = ('title', 'argos', 'hymt', 'install', 'available', 'use', 'online', 'offline')
_DOWNLOAD = {'en': 'Download now', 'ru': 'Скачать сейчас', 'es': 'Descargar ahora',
             'de': 'Jetzt herunterladen', 'fr': 'Télécharger', 'zh': '立即下载',
    'pt': 'Baixe agora',
    'it': 'Scarica ora',
}
_RUNTIME = {
    'en': 'Argos could not start. Check its installation or choose another translator.',
    'ru': 'Не удалось запустить Argos. Проверьте установку или выберите другой переводчик.',
    'es': 'Argos no pudo iniciarse. Comprueba la instalación o elige otro traductor.',
    'de': 'Argos konnte nicht starten. Installation prüfen oder einen anderen Übersetzer wählen.',
    'fr': 'Argos n’a pas pu démarrer. Vérifiez l’installation ou choisissez un autre traducteur.',
    'zh': 'Argos 无法启动。请检查安装或选择其他翻译引擎。',

    'pt': 'Argos não pôde ser iniciado. Verifique sua instalação ou escolha outro tradutor.',
    'it': 'Impossibile avviareArgos. Controlla la sua installazione o scegli un altro traduttore.',
}


def recovery_text(language, key):
    return _TEXT.get(language, _TEXT['en'])[_KEYS.index(key)]


@dataclass(frozen=True)
class MissingProvider:
    engine: str
    source: str
    target: str
    component: str = 'package'

    def message(self, language):
        if self.component == 'runtime':
            return _RUNTIME.get(language, _RUNTIME['en'])
        from languages import language_display_name
        pair = f'{language_display_name(self.source, language)} → {language_display_name(self.target, language)}'
        return recovery_text(language, self.engine).format(pair=pair)


class OfflineProviderUnavailable(RuntimeError):
    """Carry setup information from a translation worker back to its own UI."""
    def __init__(self, engine, source, target, message, *, component='package'):
        super().__init__(message)
        self.issue = MissingProvider(engine, source, target, component)


def missing_provider(engine, source, target):
    """Read small local metadata; never load a model or probe the network in Qt."""
    import translater
    engine = str(engine).lower().replace('hy-mt', 'hymt')
    if source == target and source and source != 'auto':
        return None
    if engine == 'hymt' and not translater.hymt_installed():
        return MissingProvider(engine, source, target)
    if engine == 'argos':
        pairs = translater.argos_installed_translation_pairs_fast()
        ready = any(dst == target for _src, dst in pairs) if source == 'auto' else (source, target) in pairs
        if not ready:
            return MissingProvider(engine, source, target)
    return None


def offer_provider_recovery(parent, issue, options, language='en', *, allow_download=False):
    """Return 'install', a deliberately chosen ready provider ID, or None."""
    from PyQt5 import QtWidgets
    from settings_window import DropDownCombo, modern_combo_style
    from styled_dialogs import StyledMessageBox

    box = StyledMessageBox(parent)
    box.setWindowTitle(recovery_text(language, 'title'))
    box.setIcon(box.Warning)
    box.setText(issue.message(language))
    label = QtWidgets.QLabel(recovery_text(language, 'available'), box)
    label.setObjectName('styledMessageInformation')
    combo = DropDownCombo(box)
    combo.setAccessibleName(label.text())
    combo.setToolTip(label.text())
    combo.setMinimumHeight(32)
    label.setBuddy(combo)
    for engine, name, kind in options:
        if kind == 'api':
            from api_providers import validate, ProviderError
            from main import get_cached_config
            try:
                validate(engine, get_cached_config())
            except ProviderError:
                continue
        if engine != issue.engine and missing_provider(engine, issue.source, issue.target) is None:
            kind_label = 'API' if kind == 'api' else recovery_text(language, kind)
            combo.addItem(f'{name} · {kind_label}', engine)
    combo.setStyleSheet(modern_combo_style(box._dark, 14))
    combo.set_popup_background('#20212a' if box._dark else '#f1edf4')
    box.body_layout.insertWidget(box.body_layout.count() - 1, label)
    box.body_layout.insertWidget(box.body_layout.count() - 1, combo)
    install = box.addButton(recovery_text(language, 'install'), box.AcceptRole)
    download = box.addButton(_DOWNLOAD.get(language, _DOWNLOAD['en']), box.ActionRole) if allow_download else None
    if download is not None:
        from PyQt5.QtCore import Qt
        box.button_row.removeWidget(download)
        box.body_layout.insertWidget(1, download, 0, Qt.AlignLeft)
    switch = box.addButton(recovery_text(language, 'use'), box.ActionRole)
    switch.setEnabled(combo.count() > 0)
    box.addButton(box.Cancel)
    box.setDefaultButton(install)
    box.exec_()
    clicked = box.clickedButton()
    result = ('install' if clicked is install else 'download' if download is not None and clicked is download
              else combo.currentData() if clicked is switch else None)
    box.deleteLater()
    return result
