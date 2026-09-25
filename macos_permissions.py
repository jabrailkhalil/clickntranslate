"""First-visible-start guidance for the Mac permissions used by the app."""
import logging
import sys

from PyQt5 import QtCore, QtWidgets

import macos_desktop
import platform_support
from button_styles import standard_buttons
from macos_text import macos_text
from rounded_windows import clip_rounded_window
from styled_dialogs import CenteredFramelessDialog


TEXT = {
    'en': ('Ready to translate on Mac', 'Allow access to the features you want to use. The buttons open the right macOS settings.',
           'Screen Recording', 'Accessibility', 'Enable', 'Allowed', 'Not enabled', 'Check again', 'Continue',
           'Could not open settings. Please try again.',
           'Recognize and translate text on your screen.', 'Copy and replace selected text in other apps.',
           'Allow access in macOS, then return via the Dock or Cmd+Tab. Restart the app if macOS asks you to.'),
    'ru': ('Подготовим перевод на Mac', 'Разрешите доступ к нужным функциям. Кнопки откроют нужные разделы настроек macOS.',
           'Запись экрана', 'Универсальный доступ', 'Включить', 'Разрешено', 'Не включено', 'Проверить снова', 'Продолжить',
           'Не удалось открыть настройки. Попробуйте ещё раз.',
           'Распознавание и перевод текста с экрана.', 'Копирование и замена выделенного текста в других приложениях.',
           'Разрешите доступ в macOS и вернитесь через Dock или Cmd+Tab. Если macOS попросит — перезапустите приложение.'),
    'de': ('Bereit zum Übersetzen auf dem Mac', 'Erlauben Sie den Zugriff auf die gewünschten Funktionen. Die Schaltflächen öffnen die passenden macOS-Einstellungen.',
           'Bildschirmaufnahme', 'Bedienungshilfen', 'Aktivieren', 'Erlaubt', 'Nicht aktiviert', 'Erneut prüfen', 'Weiter',
           'Die Einstellungen konnten nicht geöffnet werden. Bitte erneut versuchen.',
           'Text auf dem Bildschirm erkennen und übersetzen.', 'Ausgewählten Text in anderen Apps kopieren und ersetzen.',
           'Erlauben Sie den Zugriff in macOS und kehren Sie über das Dock oder Cmd+Tab zurück. Starten Sie die App neu, falls macOS dazu auffordert.'),
    'es': ('Prepara la traducción en Mac', 'Permite el acceso a las funciones que quieras usar. Los botones abren los ajustes de macOS correspondientes.',
           'Grabación de pantalla', 'Accesibilidad', 'Activar', 'Permitido', 'Sin activar', 'Comprobar de nuevo', 'Continuar',
           'No se pudieron abrir los ajustes. Inténtalo de nuevo.',
           'Reconocer y traducir el texto de la pantalla.', 'Copiar y reemplazar texto seleccionado en otras apps.',
           'Permite el acceso en macOS y vuelve mediante el Dock o Cmd+Tab. Reinicia la app si macOS lo solicita.'),
    'fr': ('Préparez la traduction sur Mac', 'Autorisez les fonctions que vous souhaitez utiliser. Les boutons ouvrent les réglages macOS correspondants.',
           'Enregistrement de l’écran', 'Accessibilité', 'Activer', 'Autorisé', 'Non activé', 'Vérifier à nouveau', 'Continuer',
           'Impossible d’ouvrir les réglages. Veuillez réessayer.',
           'Reconnaître et traduire le texte affiché à l’écran.', 'Copier et remplacer le texte sélectionné dans d’autres apps.',
           'Autorisez l’accès dans macOS, puis revenez via le Dock ou Cmd+Tab. Redémarrez l’app si macOS le demande.'),
    'zh': ('准备好在 Mac 上翻译', '请为需要使用的功能授权。下面的按钮会直接打开对应的 macOS 设置。',
           '屏幕录制', '辅助功能', '启用', '已允许', '未启用', '重新检查', '继续', '无法打开设置，请重试。',
           '识别并翻译屏幕上的文字。', '复制和替换其他应用中选中的文字。', '请在 macOS 中授权，然后通过程序坞或 Cmd+Tab 返回。如果系统提示，请重启应用。'),
}


class MacPermissionsDialog(CenteredFramelessDialog):
    def __init__(self, parent=None, language='en'):
        super().__init__(parent)
        self.language = language if language in TEXT else 'en'
        self.labels = TEXT[self.language]
        self.setWindowTitle(self.labels[0])
        self.setMinimumWidth(540)
        self.resize(580, 450)
        self.setWindowModality(QtCore.Qt.WindowModal)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        surface = QtWidgets.QFrame(self)
        surface.setObjectName('permissionSurface')
        layout.addWidget(surface)
        panel = QtWidgets.QVBoxLayout(surface)
        panel.setContentsMargins(24, 20, 24, 20)
        panel.setSpacing(14)
        title_row = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel(self.labels[0])
        title.setWordWrap(True)
        title.setObjectName('permissionTitle')
        title_row.addWidget(title, 1)
        close = QtWidgets.QPushButton('×')
        close.setObjectName('permissionClose')
        close.setAccessibleName(macos_text(self.language, 'later'))
        close.setFixedSize(30, 30)
        close.clicked.connect(self.reject)
        title_row.addWidget(close, 0, QtCore.Qt.AlignTop)
        panel.addLayout(title_row)
        # Keep the header and actions reachable when a large interface scale
        # leaves less room than the wrapped explanation needs on a small Mac.
        scroll = QtWidgets.QScrollArea(surface)
        scroll.setObjectName('permissionScroll')
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        body = QtWidgets.QWidget()
        body.setObjectName('permissionBody')
        content = QtWidgets.QVBoxLayout(body)
        content.setContentsMargins(0, 0, 8, 0)
        content.setSpacing(14)
        scroll.setWidget(body)
        panel.addWidget(scroll, 1)

        def paragraph(text):
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            return label

        content.addWidget(paragraph(self.labels[1]))
        self.buttons, self.status_labels = {}, {}
        for index, kind in enumerate(('screen', 'accessibility')):
            row = QtWidgets.QHBoxLayout()
            details = QtWidgets.QVBoxLayout()
            heading = QtWidgets.QLabel(self.labels[2 + index])
            heading.setWordWrap(True)
            heading.setObjectName('permissionHeading')
            details.addWidget(heading)
            details.addWidget(paragraph(self.labels[10 + index]))
            status = paragraph('')
            details.addWidget(status)
            self.status_labels[kind] = status
            row.addLayout(details, 1)
            button = QtWidgets.QPushButton(self.labels[4])
            button.setMinimumWidth(110)
            button.clicked.connect(lambda checked=False, permission=kind: self.request(permission))
            row.addWidget(button, 0, QtCore.Qt.AlignVCenter)
            self.buttons[kind] = button
            content.addLayout(row)
        content.addWidget(paragraph(self.labels[12]))
        if not getattr(sys, 'frozen', False):
            content.addWidget(paragraph(macos_text(self.language, 'python')))
        self.error_label = paragraph('')
        self.error_label.hide()
        content.addWidget(self.error_label)
        actions = QtWidgets.QHBoxLayout()
        refresh = QtWidgets.QPushButton(self.labels[7])
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        actions.addStretch()
        self.continue_button = QtWidgets.QPushButton(macos_text(self.language, 'later'))
        self.continue_button.setObjectName('primaryButton')
        self.continue_button.clicked.connect(self.accept)
        actions.addWidget(self.continue_button)
        panel.addLayout(actions)
        dark = getattr(parent, 'current_theme', 'Темная') != 'Светлая'
        background, foreground, border = ('#171322', '#eee9f4', '#66527e') if dark else ('#efebf4', '#302936', '#c5b3da')
        self.setStyleSheet(f'''
            QFrame#permissionSurface {{ background: {background}; border: 1px solid {border}; border-radius: 18px; }}
            QScrollArea, QWidget#permissionBody {{ background: transparent; border: none; }}
            QLabel {{ color: {foreground}; background: transparent; border: none; font-size: 13px; }}
            QLabel#permissionTitle {{ font-size: 19px; font-weight: bold; }}
            QLabel#permissionHeading {{ font-weight: bold; }}
        ''' + standard_buttons(dark, compact=False) + f'''
            QPushButton#permissionClose {{ background: transparent; border: none; color: {foreground}; padding: 0; font-size: 23px; }}
        ''')
        clip_rounded_window(self, surface, 18)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1500)
        self.timer.timeout.connect(self.refresh)
        self.finished.connect(self.timer.stop)
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.timer.start()

    def refresh(self):
        complete = True
        for kind in self.buttons:
            try:
                granted = macos_desktop.permission_granted(kind)
            except Exception:
                logging.exception('Could not check macOS %s permission', kind)
                granted = False
            self.buttons[kind].setEnabled(not granted)
            self.buttons[kind].setText(self.labels[5] if granted else self.labels[4])
            self.status_labels[kind].setText(('✓ ' if granted else '') + self.labels[5 if granted else 6])
            complete = complete and granted
        self.continue_button.setText(self.labels[8] if complete else macos_text(self.language, 'later'))

    def request(self, kind):
        try:
            macos_desktop.request_permission(kind)
            self.error_label.hide()
        except Exception:
            logging.exception('Could not request macOS %s permission', kind)
            self.error_label.setText(self.labels[9])
            self.error_label.show()
        self.refresh()


def maybe_show_permissions(owner):
    """One guide per visible app session; granted access is never requested again."""
    if not platform_support.IS_MAC or not owner.isVisible():
        return False
    current = getattr(owner, '_macos_permissions_dialog', None)
    if current is not None and current.isVisible():
        return True
    if getattr(owner, '_macos_permissions_prompted', False):
        return False
    owner._macos_permissions_prompted = True
    try:
        if all(macos_desktop.permission_granted(kind) for kind in ('screen', 'accessibility')):
            return False
    except Exception:
        logging.exception('Could not check startup macOS permissions')
    dialog = MacPermissionsDialog(owner, getattr(owner, 'current_interface_language', 'en'))
    owner._macos_permissions_dialog = dialog

    def finished(_result):
        owner._macos_permissions_dialog = None
        dialog.deleteLater()
        QtCore.QTimer.singleShot(150, owner._maybe_start_first_run_guide)

    dialog.finished.connect(finished)
    dialog.open()
    return True
