"""Record first LaunchServices open with download quarantine on an isolated Mac."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time
import uuid


def invoke(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, **kwargs)


def attribute(path):
    value = invoke(['/usr/bin/xattr', '-p', 'com.apple.quarantine', str(path)])
    return value.stdout.strip() if value.returncode == 0 else None


root = Path('build/macos/trace').resolve()
root.mkdir(parents=True, exist_ok=True)
candidate = Path(os.environ['CANDIDATE'])
manifest = json.loads((candidate / 'BUILD.json').read_text())
assert manifest['source_commit'] == os.environ['EXPECTED_SHA']
assert manifest['architecture'] == platform.machine()
assert manifest['workflow_run'] == os.environ['TARGET_RUN']
reference = next(f for f in manifest['files'] if f['name'].endswith('.dmg'))
receipt = {'source_sha': manifest['source_commit'], 'run': manifest['workflow_run'],
           'dmg_sha256': reference['sha256'], 'os': platform.mac_ver()[0],
           'architecture': platform.machine(), 'checked_at': datetime.now(timezone.utc).isoformat(),
           'method': 'synthetic Safari-form download quarantine, first LaunchServices open',
           'launch_timeout_seconds': 35, 'user_acknowledgment': False}
report = root / 'quarantine.json'


def save():
    report.write_text(json.dumps(receipt, ensure_ascii=False, indent=2))


save()
with tempfile.TemporaryDirectory(prefix='cnt-browser-quarantine-') as directory:
    isolated = Path(directory)
    dmg = isolated / reference['name']
    shutil.copyfile(candidate / dmg.name, dmg)
    stamp = f'0083;{int(time.time()):08X};Safari;{str(uuid.uuid4()).upper()}'
    invoke(['/usr/bin/xattr', '-w', 'com.apple.quarantine', stamp, str(dmg)], check=True)
    receipt['dmg_quarantine'] = attribute(dmg)
    assert receipt['dmg_quarantine']
    mount = isolated / 'mount'
    mount.mkdir()
    invoke(['/usr/bin/hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint',
            str(mount), str(dmg)], check=True, timeout=90)
    app = Path('/Applications/ClicknTranslate.app')
    assert not app.exists()
    try:
        invoke(['/usr/bin/sudo', '/usr/bin/ditto', str(mount / app.name), str(app)], check=True)
    finally:
        invoke(['/usr/bin/hdiutil', 'detach', str(mount)], check=True, timeout=45)
    receipt['application_quarantine_after_ditto'] = attribute(app)
    if not receipt['application_quarantine_after_ditto']:
        invoke(['/usr/bin/sudo', '/usr/bin/xattr', '-w', 'com.apple.quarantine', stamp, str(app)], check=True)
    receipt['application_quarantine_at_launch'] = attribute(app)
    assert receipt['application_quarantine_at_launch']
    invoke(['/usr/bin/codesign', '--verify', '--deep', '--strict', '-R',
            '=identifier "io.github.jabrailkhalil.clickntranslate" and certificate root = '
            'H"fc6752f0026d34e5b63433544af788b8fc1899ef"', str(app)], check=True)
    save()
    own_report = isolated / 'first-launch.json'
    started = time.monotonic()
    process = subprocess.Popen(['/usr/bin/open', '-n', '-W', '-a', str(app), '--args',
                                '--macos-permission-report', str(own_report)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(timeout=35)
        receipt['timed_out'] = False
        receipt['open_status'] = process.returncode
    except subprocess.TimeoutExpired:
        receipt['timed_out'] = True
        receipt['open_status'] = None
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    receipt.update(seconds=round(time.monotonic() - started, 2),
                   open_stdout=stdout.strip(), open_stderr=stderr.strip(),
                   application_started=own_report.is_file())
    if own_report.is_file():
        receipt['application_report'] = json.loads(own_report.read_text())
    assessment = invoke(['/usr/sbin/spctl', '--assess', '--type', 'execute', '--verbose=4', str(app)],
                        timeout=60)
    receipt['gatekeeper_status'] = assessment.returncode
    receipt['gatekeeper_verdict'] = (assessment.stdout + assessment.stderr).strip()
    receipt['application_quarantine_after_launch'] = attribute(app)
    receipt['outcome'] = ('app executed' if receipt['application_started'] else
                          'no response before timeout' if receipt['timed_out'] else
                          'LaunchServices rejected request' if receipt['open_status'] else
                          'LaunchServices returned without an application report')
    save()
    print(json.dumps(receipt, ensure_ascii=False))
