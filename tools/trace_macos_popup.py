"""Observe width and host geometry in an isolated, real Cocoa scene."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT / "src")]
import main
import language_search
import macos_smoke
import settings_window
import ui_scaling
from PyQt5 import QtCore
from PyQt5.QtTest import QTest

MODE = sys.argv[1]
DEST = ROOT / "build/macos/trace" / MODE
DEST.mkdir(parents=True,exist_ok=True)
records = []

class Finished(Exception):
    pass

def dims(size):
    return [size.width(), size.height()]

def point_rect(rect):
    return [rect.x(), rect.y(), rect.width(), rect.height()]

def record(topic, combo, **kwargs):
    popup = combo.view().window()
    proxy = popup.graphicsProxyWidget()
    widgets = [popup.layout().itemAt(i).widget() for i in range(popup.layout().count())]
    content = {
        "control": point_rect(combo.geometry()), "popup": point_rect(popup.geometry()),
        "proxy": point_rect(proxy.geometry()) if proxy is not None else None,
        "canvas": point_rect(combo.window().rect()), "popup_min": dims(popup.minimumSize()),
        "stable": dims(combo._language_popup_size) if combo._language_popup_size is not None else None,
        "children": [[w.metaObject().className(),w.isHidden(),dims(w.minimumSizeHint()),dims(w.size())] for w in widgets if w is not None],
    }
    if proxy is not None:
        content["proxy_min"] = dims(proxy.minimumSize())
        content["proxy_preferred"] = dims(proxy.preferredSize())
        content["proxy_bounds"] = point_rect(proxy.boundingRect())
    records.append({"event":topic,**content,**kwargs})

def check(main_module, app, window, report, screenshots):
    window.set_interface_language("ru")
    if window.current_theme != "Темная":
        window.toggle_theme()
    window.set_ui_scale_percent(80)
    window.show_main_screen()
    combo = window.source_lang
    content, stable = combo._popup_content_size, language_search.stable_search_popup_size
    position = settings_window.position_embedded_combo_popup
    def measured():
        size = content()
        record('content', combo, measured=dims(size))
        return size
    def stable_size(c, size):
        if MODE in ('unfiltered','both') and c is combo and not c._language_search.text():
            c._language_popup_size = None
        result = stable(c,size)
        if c is combo: record('stable', combo, desired=dims(size), result=dims(result))
        return result
    def placed(c,popup,gap,desired_size=None):
        result=position(c,popup,gap,desired_size)
        if c is combo and result and MODE in ('proxy','both'):
            proxy = popup.graphicsProxyWidget()
            anchor = QtCore.QRect(c.mapTo(c.window(),QtCore.QPoint()), c.size())
            target=ui_scaling.combo_popup_geometry(anchor,desired_size,c.window().rect(),gap,margin=4)
            proxy.resize(QtCore.QSizeF(target.size()))
        if c is combo: record('placed',combo,embedded=result,desired=dims(desired_size))
        return result
    combo._popup_content_size=measured
    language_search.stable_search_popup_size=stable_size
    settings_window.position_embedded_combo_popup=placed
    try:
        for opening in (1, 2):
            record('before '+str(opening), combo)
            combo.showPopup()
            record('after show '+str(opening), combo)
            QTest.qWait(100)
            record('settled '+str(opening), combo)
            window.grab().save(str(DEST / f"opening-{opening}.png"))
            combo.view().scrollToBottom()
            app.processEvents()
            combo.hidePopup()
            QTest.qWait(20)
    finally:
        settings_window.position_embedded_combo_popup=position
        language_search.stable_search_popup_size=stable
        (DEST / 'trace.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
        for event in records:
            if event['event'].startswith('settled') or event['event']=='content':
                print(MODE,event['event'],event['control'],event['popup'],event['proxy'],event.get('measured'))
    raise Finished

macos_smoke.dropdown_screenshots=check
try:
    macos_smoke.run(main, DEST / "screen.json")
except Finished:
    pass
