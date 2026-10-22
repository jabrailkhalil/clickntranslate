"""Dialog actions follow the chosen app language and keep their actual Qt roles."""
from string import Formatter

import pytest
from PyQt5 import QtWidgets

from assistant_text import ASSISTANT_TEXT, assistant_text
from dialog_text import LANGUAGES, dialog_action_text
from startup_dialogs import replacement_dialog
from styled_dialogs import StyledMessageBox


@pytest.fixture
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize('language,close,cancel,save', [
    ('en', 'Close', 'Cancel', 'Save'), ('ru', 'Закрыть', 'Отмена', 'Сохранить'),
    ('es', 'Cerrar', 'Cancelar', 'Guardar'), ('de', 'Schließen', 'Abbrechen', 'Speichern'),
    ('fr', 'Fermer', 'Annuler', 'Enregistrer'), ('zh', '关闭', '取消', '保存'),
    ('pt', 'Fechar', 'Cancelar', 'Salvar'), ('it', 'Chiudi', 'Annulla', 'Salva'),
])
def test_shared_close_and_standard_actions_match_parent_language(app, language, close, cancel, save):
    parent = QtWidgets.QWidget()
    parent.current_interface_language = language
    box = StyledMessageBox(parent)
    try:
        box.setStandardButtons(box.Cancel | box.Save)
        assert box.title_bar.close_button.text() == '×'
        assert box.title_bar.close_button.toolTip() == close
        assert box.title_bar.close_button.accessibleName() == close
        assert box.button(box.Cancel).text() == cancel
        assert box.button(box.Save).text() == save
        assert box.buttonRole(box.button(box.Cancel)) == box.RejectRole
        assert box.buttonRole(box.button(box.Save)) == box.AcceptRole
        box.setDefaultButton(box.Save)
        box.setEscapeButton(box.Cancel)
        assert box.button(box.Save).isDefault()
        assert box._escape_button is box.button(box.Cancel)
    finally:
        box.deleteLater()
        parent.deleteLater()


def test_explicit_language_refresh_preserves_custom_button_text_and_role(app):
    box = StyledMessageBox()
    try:
        box.setInterfaceLanguage('en')
        box.setStandardButtons(box.Yes | box.No)
        box.button(box.Yes).setText('Install this engine')
        custom = box.addButton('Keep my exact wording', box.DestructiveRole)
        box.setInterfaceLanguage('ru')
        assert box.title_bar.close_button.toolTip() == 'Закрыть'
        assert box.button(box.No).text() == 'Нет'
        assert box.button(box.Yes).text() == 'Install this engine'
        assert box.button(box.Yes).accessibleName() == 'Install this engine'
        assert custom.text() == 'Keep my exact wording'
        assert box.buttonRole(custom) == box.DestructiveRole
    finally:
        box.deleteLater()


@pytest.mark.parametrize('language', LANGUAGES)
def test_parentless_startup_dialog_uses_its_requested_language(app, language):
    box = replacement_dialog(language, '1.8.2')
    try:
        assert box.title_bar.close_button.toolTip() == dialog_action_text(box, 'Close')
        assert box._dialog_language_code == language
        assert box.buttonRole(box.replace_button) == box.AcceptRole
        assert box.buttonRole(box.existing_button) == box.RejectRole
        assert box.existing_button.isDefault()
    finally:
        box.deleteLater()


def _fields(value):
    values = value if isinstance(value, tuple) else (value,)
    return [{field for _, field, _, _ in Formatter().parse(text) if field is not None} for text in values]


@pytest.mark.parametrize('language', LANGUAGES)
def test_companion_text_has_complete_keys_and_matching_format_fields(language):
    english = ASSISTANT_TEXT['en']
    localized = ASSISTANT_TEXT[language]
    assert localized.keys() == english.keys()
    for key, value in localized.items():
        assert value, (language, key)
        assert _fields(value) == _fields(english[key]), (language, key)
    assert assistant_text(language, 'size_decrease') != assistant_text(language, 'size_increase')
    assert assistant_text(language, 'opacity_decrease') != assistant_text(language, 'opacity_increase')
