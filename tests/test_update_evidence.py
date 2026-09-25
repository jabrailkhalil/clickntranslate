import json
import zipfile

from tools.verify_update_evidence import REQUIRED, sha256, verify


def test_only_exact_artifacts_and_old_helpers_satisfy_release_gate(tmp_path):
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    archive = candidate / 'Click-n-Translate-1.8.1-windows-portable-x64.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('ClicknTranslate/ClicknTranslate.exe', b'candidate')
    setup = candidate / 'Click-n-Translate-1.8.1-windows-x64-installer.exe'
    setup.write_bytes(b'candidate installer')
    receipts = []
    for old, mode in REQUIRED:
        folder = tmp_path / (old + '-' + mode)
        folder.mkdir()
        path = folder / 'result.json'
        path.write_text(json.dumps(dict(status='passed', old_version=old, mode=mode,
            new_version='1.8.1', new_sha256=sha256(archive), new_setup_sha256=sha256(setup),
            helper_override=False, old_helper_sha256='old', invoked_helper_sha256='old',
            helper_exit_code=0, preferences_preserved=True, verified_program_files=1,
            restarted_gui_pid=10)), encoding='utf-8')
        (folder / 'restart-ready.txt').write_text('1.8.1')
        receipts.append(path)
    assert verify(candidate, '1.8.1', receipts)['passed']
    path = receipts[0]
    original = json.loads(path.read_text())
    for change in ({'helper_override': True}, {'new_sha256': 'another build'},
                   {'helper_exit_code': None}, {'preferences_preserved': False},
                   {'invoked_helper_sha256': 'new helper'}, {'status': 'failed'}):
        path.write_text(json.dumps(original | change), encoding='utf-8')
        assert not verify(candidate, '1.8.1', receipts)['passed'], change
    path.write_text(json.dumps(original), encoding='utf-8')
    (path.parent / 'restart-ready.txt').write_text('1.7.0')
    assert not verify(candidate, '1.8.1', receipts)['passed']
