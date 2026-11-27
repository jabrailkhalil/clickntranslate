"""Run every native smoke section and report every exception in a diagnostic CI job."""
import json
from pathlib import Path
import sys
import traceback

root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'src')]
import macos_smoke
import main
from PyQt5 import QtCore, QtWidgets

dest=root/'build/macos/trace'
dest.mkdir(parents=True,exist_ok=True)
records={}

def save():
    (dest/'trace.json').write_text(json.dumps(records,indent=2),encoding='utf-8')

def observe(name, original):
    def check(*args, **kwargs):
        try:
            value=original(*args, **kwargs)
        except Exception:
            records[name]=traceback.format_exc()
            print(records[name],file=sys.__stderr__,flush=True)
            active=QtWidgets.QApplication.activePopupWidget()
            if active is not None: active.hide()
            return {'error':records[name]}
        else:
            records[name]='passed'
            return value
        finally:
            save()
    return check

for stage in ('dropdown_screenshots','dialog_placement_check','popup_screenshots','translation_draft_check','main_direction_and_theme_check','capture_picker_and_notice_check','compact_translation_views_check','api_keychain_check'):
    setattr(macos_smoke,stage,observe(stage,getattr(macos_smoke,stage)))
try:
    macos_smoke.run(main,dest/'smoke.json')
except BaseException:
    records['main']=traceback.format_exc()
    print(records['main'],file=sys.__stderr__,flush=True)
finally:
    save()
if any(v!='passed' for v in records.values()):
    raise SystemExit(1)
