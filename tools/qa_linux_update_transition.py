import argparse, hashlib, json, os, re, socket, struct, subprocess, sys, time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='Verify manual Linux AppImage replacement with real public binaries and isolated user data.')
parser.add_argument('--new-version', required=True)
args = parser.parse_args()
if not re.fullmatch(r'1\.\d+\.\d+', args.new_version): parser.error('Invalid version')
case = root / 'build/linux-update-audit' / ('1.7.0-to-' + args.new_version)
case.mkdir(parents=True)
sys.path.insert(0, str(root))
import single_instance
from qa_published_update import download, release
old, _ = download(release('1.7.0'), 'Click-n-Translate-1.7.0-linux-x86_64.AppImage', case)
new, _ = download(release(args.new_version), 'Click-n-Translate-' + args.new_version + '-linux-x86_64.AppImage', case)
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()
assert sha(old) == 'f2863c22964220b7d163681634e99fd203586e3b3729900b4b6fa80644960547'
old.chmod(0o755)
new.chmod(0o755)
env = dict(os.environ, QT_QPA_PLATFORM='xcb')
for key in ('XDG_DATA_HOME','XDG_CACHE_HOME','XDG_CONFIG_HOME','XDG_RUNTIME_DIR'):
    folder = case / key.lower()
    folder.mkdir(mode=0o700)
    env[key] = str(folder)
data_root = Path(env['XDG_DATA_HOME'])/'clickntranslate'
data = data_root/'data'
data.mkdir(parents=True)
config = dict(interface_language='ru',ui_scale_percent=100,theme='Светлая',
              update_check_on_launch=False,show_update_info=False,first_run_guide_completed=True,
              first_run_guide_pending=False,autostart=False,start_minimized=False,
              desktop_assistant_enabled=False,hotkey_defaults_revision=5,audit_marker='linux-real-170-181')
for key in ('copy_hotkey','translate_hotkey','fullscreen_translate_hotkey','translate_selection_hotkey',
            'translate_replace_selection_hotkey','game_translate_hotkey','toggle_window_hotkey'):
    config[key] = ''
(data/'config.json').write_text(json.dumps(config),encoding='utf-8')
markers = {}
for relative in ('data/update-marker.bin','ocr/model-marker.bin','translators/model-marker.bin'):
    p = data_root/relative
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(('preserve:'+relative).encode())
    markers[relative] = sha(p)
report = dict(status='running',scope='Manual AppImage replacement, real published GUIs; no automatic Linux updater',
              old_sha256=sha(old),new_sha256=sha(new),launches=[])
try:
    for index,(binary,version) in enumerate(((old,'1.7.0'),(new,args.new_version),(new,args.new_version))):
        ack = case/f'ready-{index}.txt'
        channel = str(Path(env['XDG_RUNTIME_DIR'])/'clickntranslate.sock')
        with (case/f'launch-{index}.log').open('w') as log:
            proc = subprocess.Popen([str(binary),'--appimage-extract-and-run','--show-after-update','--update-ack='+str(ack)],
                                    cwd=case,env=env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+90
                while not ack.exists() and proc.poll() is None and time.monotonic()<deadline: time.sleep(.1)
                assert ack.is_file(), (version,'GUI readiness absent',proc.poll())
                assert ack.read_text().strip()==version
                with socket.socket(socket.AF_UNIX) as client:
                    client.connect(channel)
                    pid,_,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                assert single_instance.send_command_status('show',channel) is single_instance.CommandStatus.ACCEPTED
                time.sleep(2)
                assert proc.poll() is None
                assert single_instance.send_command_status('quit',channel,target_pid=pid) is single_instance.CommandStatus.ACCEPTED
                assert proc.wait(timeout=20)==0
                actual=json.loads((data/'config.json').read_text())
                for key in ('interface_language','ui_scale_percent','theme','autostart','audit_marker'):
                    assert actual[key]==config[key],key
                for relative,expected in markers.items(): assert sha(data_root/relative)==expected,relative
                report['launches'].append(dict(version=version,ready=True,graceful_exit=True,preferences_preserved=True,markers_preserved=True))
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=10)
    report['status']='passed'
except Exception as e:
    report['status']='failed'
    report['error']=repr(e)
    raise
finally:
    (case/'result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)
