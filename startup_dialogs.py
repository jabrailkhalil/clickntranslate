"""Startup choices use the same chrome, theme and scale as the running app."""

import logging
from PyQt5 import QtCore
from styled_dialogs import StyledMessageBox


TEXT = {
    'en': ('The app is already running', 'Close the running copy and open this one?',
           'Version {version} will open. Windows belonging to the previous copy will close.',
           'Close and start', 'Open running app', 'Closing the previous copy…', 'Please wait…',
           'Could not close the previous copy. Close it from its tray menu and try again.'),
    'ru': ('Программа уже запущена', 'Закрыть работающую копию и открыть эту?',
           'Будет запущена версия {version}. Окна предыдущей копии закроются.',
           'Закрыть и запустить', 'Открыть работающую', 'Закрываем предыдущую копию…', 'Подождите…',
           'Не удалось закрыть предыдущую копию. Выйдите из неё через меню в трее и повторите запуск.'),
    'de': ('Die App läuft bereits', 'Die laufende Kopie schließen und diese öffnen?',
           'Version {version} wird geöffnet. Die Fenster der bisherigen Kopie werden geschlossen.',
           'Schließen und starten', 'Laufende App öffnen', 'Bisherige Kopie wird geschlossen…', 'Bitte warten…',
           'Die bisherige Kopie konnte nicht beendet werden. Beenden Sie sie über das Tray-Menü und versuchen Sie es erneut.'),
    'fr': ('L’application est déjà ouverte', 'Fermer la copie active et ouvrir celle-ci ?',
           'La version {version} sera ouverte. Les fenêtres de la copie précédente seront fermées.',
           'Fermer et démarrer', 'Ouvrir l’app active', 'Fermeture de la copie précédente…', 'Veuillez patienter…',
           'Impossible de fermer la copie précédente. Quittez-la depuis la zone de notification, puis réessayez.'),
    'es': ('La aplicación ya está abierta', '¿Cerrar la copia activa y abrir esta?',
           'Se abrirá la versión {version}. Se cerrarán las ventanas de la copia anterior.',
           'Cerrar e iniciar', 'Abrir la app activa', 'Cerrando la copia anterior…', 'Espera…',
           'No se pudo cerrar la copia anterior. Ciérrala desde el menú de la bandeja e inténtalo de nuevo.'),
    'zh': ('程序已在运行', '关闭正在运行的副本并打开此副本？',
           '将打开 {version} 版本。之前副本的窗口将关闭。',
           '关闭并启动', '打开运行中的程序', '正在关闭之前的副本…', '请稍候…',
           '无法关闭之前的副本。请从托盘菜单退出后重试。'),
}


def replacement_dialog(language, version):
    labels = TEXT.get(language, TEXT['en'])
    box = StyledMessageBox()
    box.setWindowTitle(labels[0])
    box.setText(labels[1])
    box.setInformativeText(labels[2].format(version=version))
    box.setIcon(StyledMessageBox.Question)
    box.replace_button = box.addButton(labels[3], StyledMessageBox.AcceptRole)
    box.replace_button.setObjectName('primaryButton')
    box.existing_button = box.addButton(labels[4], StyledMessageBox.RejectRole)
    box.setDefaultButton(box.existing_button)
    box.setEscapeButton(box.existing_button)
    return box


def ask_replacement(language, version):
    box = replacement_dialog(language, version)
    box.exec_()
    replace = box.clickedButton() is box.replace_button
    box.deleteLater()
    return replace


class _CloseWorker(QtCore.QThread):
    def __init__(self, close):
        super().__init__()
        self.close = close
        self.succeeded = False

    def run(self):
        try:
            self.succeeded = bool(self.close())
        except Exception:
            logging.exception('Could not replace the running app')


class _ClosingDialog(StyledMessageBox):
    def reject(self):
        # Shutdown has already been requested. Keep this short wait visible;
        # closing it must not leave a running worker without its Qt owner.
        pass


def close_with_progress(language, close):
    labels = TEXT.get(language, TEXT['en'])
    box = _ClosingDialog()
    box.setWindowTitle(labels[0])
    box.setText(labels[5])
    box.setIcon(StyledMessageBox.Information)
    box.addButton(labels[6], StyledMessageBox.ActionRole).setEnabled(False)
    box.title_bar.close_button.setEnabled(False)
    worker = _CloseWorker(close)
    worker.finished.connect(box.accept)
    worker.start()
    box.exec_()
    worker.wait()
    succeeded = worker.succeeded
    box.deleteLater()
    worker.deleteLater()
    return succeeded


def show_replacement_error(language):
    labels = TEXT.get(language, TEXT['en'])
    StyledMessageBox.warning(None, labels[0], labels[7])
