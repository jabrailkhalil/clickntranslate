from types import SimpleNamespace
from unittest import mock
import pytest

import settings_window as settings


@pytest.mark.parametrize('engine',('tesseract','rapidocr','easyocr','hymt'))
@pytest.mark.parametrize('outcome',('ready','failed','cancelled'))
def test_updates_never_switch_the_selected_provider(engine,outcome):
    owner=SimpleNamespace(parent=SimpleNamespace(current_interface_language='en'),
        _restore_settings_view=mock.Mock(),_restore_parent_topmost_after_tesseract_install=mock.Mock(),
        _set_ocr_combo_silently=mock.Mock(),save_ocr_engine=mock.Mock(),
        _set_translator_combo_silently=mock.Mock(),auto_save_setting=mock.Mock())
    setattr(owner,'_component_'+engine+'_select_on_success',False)
    setattr(owner,'_finish_'+engine+'_install_state',mock.Mock())
    setattr(owner,'_hide_'+engine+'_progress',mock.Mock())
    setattr(owner,'_reset_'+engine+'_runtime_cache',mock.Mock())
    function=getattr(settings.SettingsWindow,'_on_'+engine+'_install_'+outcome)
    args=('/does-not-exist/tesseract.exe',) if outcome=='ready' and engine=='tesseract' else ('QA failure',) if outcome=='failed' else ()
    with mock.patch.object(settings.QMessageBox,'information'),mock.patch.object(settings.QMessageBox,'warning'):
        function(owner,*args)
    owner._set_ocr_combo_silently.assert_not_called()
    owner.save_ocr_engine.assert_not_called()
    owner._set_translator_combo_silently.assert_not_called()
    owner.auto_save_setting.assert_not_called()
