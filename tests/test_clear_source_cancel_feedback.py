"""Deleting an online source cancels quietly instead of reporting an Argos install."""
from unittest import mock

import main
from test_desktop_ux import app, window


def test_clear_online_source_drains_cancellation_without_an_argos_dialog(window):
    window.text_input.setPlainText('source which is still translating')
    window._show_inline_main_result('partial result', 'source which is still translating', 'en', 'ar')
    window._main_translation_running = True
    window._main_active_engine = 'google'
    window._main_active_request = ('source which is still translating', 'en', 'ar')
    window.text_input.clear()
    assert window._main_discard_result and window._argos_cancel_requested.is_set()
    with mock.patch.object(main.QMessageBox, 'information') as message:
        window._on_argos_translation_cancelled()
    assert not window._main_translation_running
    assert window.main_result_view.toPlainText() == ''
    message.assert_not_called()
