"""Run ClicknTranslate desktop integrations against only this job's TextEdit fixtures."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
import AppKit
import ApplicationServices as AX
import Quartz
from PyQt5 import QtCore, QtWidgets
from PIL import Image
import pyperclip
from clipboard_preservation import ClipboardPreservation
import main
import macos_desktop
import macos_ocr
from macos_capture import OverlayCapture
import platform_support
from selection_platform import read_selected_text

assert os.environ.get('GITHUB_ACTIONS')=='true', 'Use an isolated hosted test Mac'
out=root/'build/macos/trace'
out.mkdir(parents=True,exist_ok=True)
report={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'stage':'start','source_permissions':{k:macos_desktop.permission_granted(k) for k in ('screen','accessibility')}}
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
marker=QtWidgets.QLabel("ClicknTranslate QA controller")
marker.setAttribute(QtCore.Qt.WA_ShowWithoutActivating,True)
marker.move(0,0); marker.show(); app.processEvents()

def wait_for(test,seconds=8):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        app.processEvents()
        result=test()
        if result: return result
        time.sleep(.04)
    raise AssertionError('condition timed out during '+report['stage'])

def attribute(obj,key):
    error,value=AX.AXUIElementCopyAttributeValue(obj,key,None)
    return value if not error else None

def expected_window(stem):
    front=AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if front is None or str(front.bundleIdentifier())!='com.apple.TextEdit': return None
    target=macos_desktop.foreground_target()
    if target and stem in str(attribute(target[1], AX.kAXTitleAttribute)):
        return target
    return None

def editor_value(pid):
    editor=attribute(AX.AXUIElementCreateApplication(pid),AX.kAXFocusedUIElementAttribute)
    return str(attribute(editor,AX.kAXValueAttribute)).strip() if editor is not None else ''

def fixture(directory,stem,text):
    path=directory/(stem+'.rtf')
    path.write_text(r'{\rtf1\ansi\deff0{\fonttbl{\f0 Helvetica;}}\f0\fs60 '+text+'}',encoding='ascii')
    subprocess.run(['/usr/bin/open','-a','TextEdit',str(path)],check=True)
    return wait_for(lambda:expected_window(stem),20)

def screen_and_window(pid,stem):
    windows=Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,Quartz.kCGNullWindowID) or []
    for w in windows:
        if int(w.get(Quartz.kCGWindowOwnerPID,0))!=pid or int(w.get(Quartz.kCGWindowLayer,100))!=0: continue
        if stem not in str(w.get(Quartz.kCGWindowName,'')): continue
        r=w[Quartz.kCGWindowBounds]
        bounds=tuple(round(r[k]) for k in ('X','Y','Width','Height'))
        region=QtCore.QRect(*bounds)
        screen=app.screenAt(region.center())
        if screen is None: continue
        frame=region.intersected(screen.geometry())
        return screen.geometry().getRect(),frame.getRect(),screen.devicePixelRatio()
    return None

def run():
    original='LANTERN COCOA TEXT'
    translated='VERIFIED TEXTEDIT REPLACEMENT'
    sentinel='ClicknTranslate disposable clipboard'
    assert all(report['source_permissions'].values())
    with tempfile.TemporaryDirectory(prefix='cnt-textedit-') as directory:
        report['stage']='frontmost TextEdit fixture'
        pid,window=fixture(Path(directory),'CNT-External-Fixture-A',original)
        target=(pid,window)
        assert wait_for(lambda:editor_value(pid)==original)
        report['source_test_target']='com.apple.TextEdit'
        report['stage']='ScreenCaptureKit capture of foreign window'
        screen_rect,region,density=wait_for(lambda:screen_and_window(pid,'CNT-External-Fixture-A'))
        with ThreadPoolExecutor(max_workers=1) as executor:
            f=executor.submit(OverlayCapture().capture,screen_rect,region,density)
            wait_for(f.done,20)
            image=f.result()
        size=(image.width(),image.height())
        assert min(size)>0
        captured=out/'textedit-region.png'
        assert image.save(str(captured))
        report['stage']='Vision recognizes foreign fixture'
        with Image.open(captured) as bitmap:
            recognized=' '.join(item[1] for item in macos_ocr.recognize_image(bitmap,'en')).upper()
        assert original in recognized, recognized
        report['screen_capture']={'path':'ScreenCaptureKit','region':region,'pixel_dimensions':size,'density':density,'vision_read_fixture':True}
        report['stage']='select real text in focused editor'
        assert macos_desktop.send_edit_shortcut('a',validate_target=lambda:bool(expected_window('CNT-External-Fixture-A')))
        assert wait_for(lambda:read_selected_text()==original)
        assert platform_support.copy_text(sentinel)
        assert read_selected_text()==original and pyperclip.paste()==sentinel
        report['accessibility_read']={'path':'AXSelectedText','fixture':True,'clipboard_unchanged':True}
        report['stage']='replace through real Cmd+C and Cmd+V'
        saved=ClipboardPreservation(pyperclip.paste,platform_support.copy_text)
        ok,reason=main.replace_selected_text_in_foreground(original,translated,target,clipboard_preservation=saved)
        assert (ok,reason)==(True,'replaced'),(ok,reason)
        wait_for(lambda:editor_value(pid)==translated)
        assert saved.restore() and pyperclip.paste()==sentinel
        report['replacement']={'action':'Cmd+C and Cmd+V','textedit_value_verified':True,'clipboard_restored':True}
        report['stage']='reject a change of focused document'
        other='SECOND DOCUMENT UNCHANGED'
        new_pid,new_win=fixture(Path(directory),'CNT-External-Fixture-B',other)
        assert new_pid==pid and wait_for(lambda:editor_value(pid)==other)
        rejected=main.replace_selected_text_in_foreground(translated,'unexpected replacement',target)
        assert tuple(rejected)==(False,'focus_changed') and editor_value(pid)==other and pyperclip.paste()==sentinel
        report['focus_change']={'same_application_different_window':True,'reason':rejected[1],'document_unchanged':True}
    report['stage']='passed'

try:
    run()
except BaseException:
    report['error']=traceback.format_exc()
    print(report['error'],file=sys.__stderr__,flush=True)
finally:
    (out/'external-textedit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
if report['stage']!='passed': raise SystemExit(1)
