"""Native clips retain every painted edge; embedded popups keep the backdrop."""
from pathlib import Path
import sys
import subprocess

import pytest
from unittest import mock
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtTest import QTest

from classic_style import classic_palette
from rounded_windows import rounded_clip_region
from settings_window import DropDownCombo, modern_combo_style
from styled_dialogs import (_apply_rounded_popup_mask, _ensure_control_tooltip,
    _paint_hover_tooltip, tooltip_has_text, tooltip_text, install_tooltip_style)
from test_desktop_ux import app, window


def painted_surface(size, radius, *, density=1., dark=True):
    image = QtGui.QImage(round(size.width()*density), round(size.height()*density),
                        QtGui.QImage.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(density)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    colors = classic_palette(dark)
    painter.setBrush(QtGui.QColor(colors['field']))
    painter.setPen(QtGui.QPen(QtGui.QColor(colors['border']), 1))
    painter.drawRoundedRect(QtCore.QRectF(QtCore.QPointF(), QtCore.QSizeF(size)).adjusted(.5,.5,-.5,-.5), radius, radius)
    painter.end()
    return image


def assert_mask_keeps_paint(mask, image):
    density = image.devicePixelRatio()
    mask=QtGui.QTransform.fromScale(density,density).map(mask)
    clipped = [(x,y) for y in range(image.height()) for x in range(image.width())
               if image.pixelColor(x,y).alpha()>8
               and not mask.contains(QtCore.QPoint(x,y))]
    assert not clipped, clipped[:10]


@pytest.mark.parametrize('radius', [4.,5.,8.,10.,15.])
@pytest.mark.parametrize('density', [1.,1.25,1.5,2.])
def test_rounded_clip_keeps_the_entire_antialiased_outline(app, radius, density):
    size=QtCore.QSize(105,65)
    mask=rounded_clip_region(QtCore.QRect(QtCore.QPoint(),size), radius, inset=.5, stroke_width=1.)
    assert_mask_keeps_paint(mask, painted_surface(size,radius,density=density))
    assert mask.contains(QtCore.QPoint(size.width()//2,size.height()//2))


@pytest.mark.parametrize('dark', [True,False])
@pytest.mark.parametrize('factor', [.8,1.,1.25,1.5,2.])
def test_real_dropdown_uses_its_painted_radius_for_all_four_mask_corners(app,dark,factor):
    combo=DropDownCombo()
    combo.setFixedSize(round(240*factor),round(28*factor))
    combo.setStyleSheet(modern_combo_style(dark,round(14*factor)))
    combo.set_popup_background(classic_palette(dark)['field'])
    combo.addItems(['First choice','Another choice','Last choice'])
    combo.setCurrentIndex(2)
    combo.show();app.processEvents();combo.showPopup()
    for _ in range(4): app.processEvents()
    popup=combo.view().window()
    try:
        radius=popup.property('roundedPopupRadius')
        assert radius==round(5*max(.75,min(3.,round(14*factor)/14)))
        _apply_rounded_popup_mask(popup)
        mask=popup.mask() if not popup.mask().isEmpty() else QtGui.QRegion(popup.rect())
        assert_mask_keeps_paint(mask,painted_surface(popup.size(),radius,dark=dark))
        if sys.platform in ('win32','darwin'): assert popup.mask().isEmpty()
        view_bounds=QtCore.QRect(combo.view().viewport().mapTo(popup,QtCore.QPoint()),combo.view().viewport().size())
        assert view_bounds.top()>=3 and view_bounds.bottom()<popup.height()-2
        image=popup.grab().toImage()
        for x,y in ((0,0),(image.width()-1,0),(0,image.height()-1),(image.width()-1,image.height()-1)):
            assert image.pixelColor(x,y).alpha()<10
    finally:
        combo.hidePopup();combo.close();combo.deleteLater()


@pytest.mark.parametrize('locale', ['en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id'])
@pytest.mark.parametrize('dark',[True,False])
def test_embedded_dropdown_border_corners_survive_all_interface_scales(window,app,locale,dark):
    from settings_sections import PAGE_TRANSLATION
    from ui_scaling import widget_global_rect
    window.set_interface_language(locale)
    if (window.current_theme!='Светлая')!=dark: window.toggle_theme()
    window.show_settings();settings=window.settings_window;settings._set_settings_page(PAGE_TRANSLATION)
    combo=settings.result_window_control
    for scale in (80,100,125,150,200):
        window.set_ui_scale_percent(scale)
        for _ in range(4): app.processEvents()
        before=window.grab().toImage()
        combo.showPopup()
        for _ in range(4): app.processEvents()
        popup=combo.view().window()
        assert popup.graphicsProxyWidget() is not None
        assert popup.mask().isEmpty()
        # A transparent corner must show the real page, not clear its scene.
        picture=window.grab();after=picture.toImage();bounds=widget_global_rect(popup)
        point=window.mapFromGlobal(bounds.topLeft())*picture.devicePixelRatio()
        if 0<=point.x()<after.width() and 0<=point.y()<after.height():
            assert after.pixelColor(point)==before.pixelColor(point), (locale,dark,scale,point)
        if locale in ('ru','ar') and scale==100:
            picture.save(str(Path(sys.argv[0]).parent/f'rounded-result-{locale}-{dark}.png'))
        combo.hidePopup()


@pytest.mark.parametrize('empty',['','  \n','<qt><div style="width:240px"> </div></qt>','\u2068\u2069'])
def test_empty_tooltip_markup_never_becomes_a_blank_grey_bubble(app,empty):
    assert not tooltip_has_text(empty)
    assert tooltip_text(empty)==''
    button=QtWidgets.QPushButton('Ouvrir')
    button.setAccessibleDescription('Ouvrir un document enregistré.')
    button.setToolTip(empty)
    _ensure_control_tooltip(button)
    assert tooltip_has_text(button.toolTip())
    assert 'Ouvrir un document' in button.toolTip()
    class FakeTip:
        hidden=False
        def text(self): return empty
        def hide(self): self.hidden=True
    tip=FakeTip();_paint_hover_tooltip(tip)
    assert tip.hidden
    button.deleteLater()


@pytest.mark.parametrize('locale',['en','ru','es','de','fr','zh','pt','it','ar','tr','hi','id'])
@pytest.mark.parametrize('dark',[True,False])
@pytest.mark.parametrize('factor',[1.,1.25,2.])
def test_actual_tooltip_has_visible_localized_ink_in_both_themes(app,locale,dark,factor):
    from settings_window import settings_text
    from styled_dialogs import _uses_dark_theme
    old_theme=app.property('ui_theme')
    owner=QtWidgets.QWidget()
    owner.setProperty('ui_effective_scale',factor)
    button=QtWidgets.QPushButton('Tip',owner)
    button.setGeometry(10,10,80,28)
    owner.resize(240,80)
    owner.show();app.processEvents()
    try:
        app.setProperty('ui_theme','Темная' if dark else 'Светлая')
        install_tooltip_style(app,dark)
        help_text=settings_text(locale,'result_window_tooltip')
        button.setToolTip(tooltip_text(help_text))
        anchor=button.mapToGlobal(button.rect().center())
        QtWidgets.QToolTip.showText(anchor,button.toolTip(),button)
        QTest.qWait(20)
        tips=[item for item in app.topLevelWidgets() if item.metaObject().className()=='QTipLabel' and item.isVisible()]
        assert tips, (locale,dark,factor)
        tip=tips[0];picture=tip.grab();image=picture.toImage()
        assert tooltip_has_text(tip.text())
        ink=sum(1 for y in range(image.height()) for x in range(image.width())
                if image.pixelColor(x,y).alpha()>100
                and ((image.pixelColor(x,y).lightness()>180) if dark else (image.pixelColor(x,y).lightness()<100)))
        assert ink>20, (locale,dark,factor,image.size(),tip.text())
        if locale in ('ru','ar') and factor==1.:
            picture.save(str(Path(sys.argv[0]).parent/f'tooltip-{locale}-{dark}.png'))
        tip.hide()
    finally:
        QtWidgets.QToolTip.hideText();owner.close();owner.deleteLater()
        app.setProperty('ui_theme',old_theme);install_tooltip_style(app,_uses_dark_theme())


def test_popup_row_tooltip_respects_disabled_hover_help(app):
    from combo_popup import PopupRowDelegate
    old=app.property('buttonTooltipsEnabled')
    combo=DropDownCombo();combo.addItem('Long translated row label')
    delegate=combo.itemDelegate();option=QtWidgets.QStyleOptionViewItem()
    option.rect=QtCore.QRect(0,0,30,28)
    event=QtGui.QHelpEvent(QtCore.QEvent.ToolTip,QtCore.QPoint(5,5),QtCore.QPoint(100,100))
    try:
        app.setProperty('buttonTooltipsEnabled',False)
        with mock.patch.object(QtWidgets.QToolTip,'showText') as show:
            assert delegate.helpEvent(event,combo.view(),option,combo.model().index(0,0)) is False
            show.assert_not_called()
    finally:
        app.setProperty('buttonTooltipsEnabled',old);combo.deleteLater()


@pytest.mark.parametrize('dark',[True,False])
@pytest.mark.parametrize('locale',['ru','ar'])
def test_actual_frameless_dialogs_keep_transparent_corners_and_full_frames(window,app,dark,locale):
    import main
    from assistant_settings import AssistantActionsDialog
    from desktop_assistant import AssistantMenu
    window.set_interface_language(locale)
    if (window.current_theme!='Светлая')!=dark: window.toggle_theme()
    dialogs=[AssistantActionsDialog(window),
             main.TranslationResultDialog(window,'Result',auto_copy=False,lang=locale,
                                          source_text='Source',source_lang='en',target_lang='ru'),
             main.DocumentTranslationDialog(window),
             main.WelcomeDialog(window), main.HotkeyLanguageDialog(window),
             AssistantMenu(locale,dark)]
    try:
        for dialog in dialogs:
            dialog.show()
            for _ in range(6): app.processEvents()
            assert dialog.mask().isEmpty()
            image=dialog.grab().toImage()
            corners=[image.pixelColor(x,y).alpha() for x,y in
                     ((0,0),(image.width()-1,0),(0,image.height()-1),(image.width()-1,image.height()-1))]
            assert max(corners)<10,(type(dialog).__name__,locale,dark,corners)
            dialog.hide()
    finally:
        for dialog in dialogs:
            dialog.close();dialog.deleteLater()


def test_tooltip_copy_formatting_does_not_require_or_create_a_gui_application():
    code='''from PyQt5.QtWidgets import QApplication
from styled_dialogs import tooltip_has_text, tooltip_text
assert QApplication.instance() is None
assert not tooltip_has_text('<qt><div> </div></qt>')
assert tooltip_text('<qt><div> </div></qt>') == ''
assert tooltip_has_text('<qt><div>Ouvrir un document.</div></qt>')
assert 'Ouvrir un document.' in tooltip_text('<qt><div>Ouvrir un document.</div></qt>')
assert QApplication.instance() is None
print('headless tooltip formatting passed')
'''
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert 'headless tooltip formatting passed' in result.stdout
