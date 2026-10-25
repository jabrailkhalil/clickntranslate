"""Large histories keep all data while constructing only reachable cards."""
import json

import pytest
from PyQt5 import QtCore, QtGui, QtWidgets, sip
from PyQt5.QtTest import QTest

import settings_window as settings_module
from history_paging import HistoryCardPager
from test_desktop_ux import app, window


def settle(app):
    for _ in range(6):
        app.processEvents()


def luminance(color):
    def linear(value):
        return value/12.92 if value<=.04045 else ((value+.055)/1.055)**2.4
    return sum(weight*linear(value) for weight,value in zip(
        (.2126,.7152,.0722),(color.redF(),color.greenF(),color.blueF())))


@pytest.fixture(params=[False, True], ids=['translation', 'copy'])
def history(window, app, tmp_path, monkeypatch, request):
    copy_mode = request.param
    records=[dict(timestamp=f'2026-10-25T12:{index//60:02}:{index%60:02}',
                  text=f'Copy {index}', original=f'Source {index}',
                  translated=f'Result {index}', language='en') for index in range(500)]
    path=tmp_path/'history.json'
    path.write_text(json.dumps(records), encoding='utf-8')
    monkeypatch.setattr(settings_module, 'get_data_file', lambda _name: str(path))
    window.show_settings()
    settings=window.settings_window
    show=settings.show_copy_history_view if copy_mode else settings.show_history_view
    show()
    settle(app)
    prefix='copy_history' if copy_mode else 'history'
    return settings, prefix, path, records, show


def pager_for(settings, prefix):
    return getattr(settings, prefix+'_cards_layout')._history_pager


def test_first_open_is_bounded_and_scrolling_reaches_every_record(history, app):
    settings, prefix, path, records, _show=history
    pager=pager_for(settings,prefix)
    assert len(pager.cards) == HistoryCardPager.BATCH_SIZE
    assert getattr(settings,prefix+'_count_label').text() == '500'
    assert pager.records == records
    bar=pager.scroll.verticalScrollBar()
    while pager._next >= 0:
        before=len(pager.cards)
        bar.setValue(bar.maximum())
        settle(app)
        assert before < len(pager.cards) <= before+HistoryCardPager.BATCH_SIZE
    assert len(pager.cards)==500
    indices=[card.findChild(QtWidgets.QPushButton,'historyDeleteButton').property('recordIndex')
             for card in pager.cards]
    assert indices==list(reversed(range(500)))
    assert json.loads(path.read_text(encoding='utf-8')) == records


def test_old_queued_batch_cannot_reappear_after_leaving_and_reopening(history, app):
    settings,prefix,_path,_records,show=history
    old=pager_for(settings,prefix)
    old.schedule()
    settings._return_from_secondary_view()
    assert old._stopped
    old._maybe_append()
    show()
    settle(app)
    current=pager_for(settings,prefix)
    assert current is not old and len(current.cards)==HistoryCardPager.BATCH_SIZE
    assert len(old.cards)==HistoryCardPager.BATCH_SIZE


def test_clearing_history_invalidates_pending_batches(history, app):
    settings,prefix,path,_records,_show=history
    old=pager_for(settings,prefix)
    old.schedule()
    (settings.clear_copy_history if prefix=='copy_history' else settings.clear_history)()
    settle(app)
    assert old._stopped
    assert json.loads(path.read_text(encoding='utf-8')) == []
    assert getattr(settings,prefix+'_record_cards') == []
    assert getattr(settings,prefix+'_count_label').text() == '0'
    assert getattr(settings,prefix+'_cards_layout')._history_pager is None


def test_theme_refresh_reuses_loaded_cards_and_scroll_position(history, app):
    settings,prefix,_path,_records,_show=history
    pager=pager_for(settings,prefix)
    bar=pager.scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    settle(app)
    cards=tuple(pager.cards)
    position=bar.value()
    for _ in range(2):
        settings.parent.toggle_theme()
        settle(app)
        assert pager_for(settings,prefix) is pager
        assert tuple(pager.cards)==cards
        assert bar.value()==position
        color=pager.cards[0].grab().toImage().pixelColor(8,8)
        assert (color.lightness()<100) is (settings.parent.current_theme!='Светлая')
        ink=getattr(settings,prefix+'_count_label').palette().color(QtGui.QPalette.WindowText)
        surface=settings.secondary_view_shell.grab().toImage().pixelColor(5,5)
        values=sorted((luminance(ink),luminance(surface)))
        assert (values[1]+.05)/(values[0]+.05)>=4.5


def test_tab_from_the_last_materialized_card_loads_the_next_batch(history, app):
    settings,prefix,_path,_records,_show=history
    pager=pager_for(settings,prefix)
    last=pager._last_button
    last.setFocus(QtCore.Qt.TabFocusReason)
    QTest.keyClick(last,QtCore.Qt.Key_Tab)
    settle(app)
    assert len(pager.cards)>=2*HistoryCardPager.BATCH_SIZE
    target=pager.cards[HistoryCardPager.BATCH_SIZE].findChild(QtWidgets.QPushButton,'historyCopyButton')
    assert settings.parent.ui_root.focusWidget() is target


def test_deleted_scroll_rejects_delayed_callbacks(history, app):
    settings,prefix,_path,_records,_show=history
    pager=pager_for(settings,prefix)
    scroll=pager.scroll
    scroll.deleteLater()
    app.sendPostedEvents(None,QtCore.QEvent.DeferredDelete)
    assert sip.isdeleted(scroll)
    # The signal-owning QObject and its timer are destroyed with the viewport.
    assert sip.isdeleted(pager)


def test_rebuilt_history_materializes_enough_rows_to_restore_the_scroll(history, app):
    settings,prefix,_path,_records,show=history
    old=pager_for(settings,prefix)
    bar=old.scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    settle(app)
    position=bar.maximum()-100
    bar.setValue(position)
    settle(app)
    show()
    current=pager_for(settings,prefix)
    assert current is not old and len(current.cards)==HistoryCardPager.BATCH_SIZE
    current.restore_position(position)
    for _ in range(30):
        app.processEvents()
        if current._restore_to is None:
            break
    assert current.scroll.verticalScrollBar().value()==position
    assert len(current.cards)>HistoryCardPager.BATCH_SIZE


def test_short_rows_load_until_the_viewport_is_filled(app):
    scroll=QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.resize(300,600)
    content=QtWidgets.QWidget()
    layout=QtWidgets.QVBoxLayout(content)
    layout.setContentsMargins(0,0,0,0)
    layout.setSpacing(0)
    layout.addStretch(1)
    scroll.setWidget(content)
    def create(record,index):
        label=QtWidgets.QLabel(str(record))
        label.setFixedHeight(10)
        layout.addWidget(label)
        return label
    pager=HistoryCardPager(scroll,layout,list(range(200)),create,lambda:True,lambda _pager:None)
    try:
        scroll.show()
        pager.append_batch()
        settle(app)
        # Fill the viewport plus the half-page prefetch margin, leaving data lazy.
        assert len(pager.cards)==100
        assert scroll.verticalScrollBar().maximum()>0
        assert pager._next>=0
    finally:
        pager.stop()
        scroll.close()
        scroll.deleteLater()
