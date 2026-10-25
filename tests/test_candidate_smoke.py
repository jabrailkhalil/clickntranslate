"""Candidate diagnostics must isolate import-time writes as well as UI writes."""
import json
from pathlib import Path
import subprocess
import sys


def test_candidate_entrypoint_isolates_import_time_diagnostics(tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = tmp_path / 'result.json'
    code = r'''
import json, sys
from pathlib import Path
root, result = Path(sys.argv[1]), Path(sys.argv[2])
sys.path[:0] = [str(root), str(root / 'src')]
sys.argv = [str(root / 'main.py'), '--candidate-smoke-test', str(result)]
import main
import candidate_smoke
import portable_paths
profile = Path(portable_paths.portable_base_dir())
assert profile.name.startswith('cnt-candidate-startup-')
assert profile != root and profile.is_dir()
marker = Path(main.get_data_file('candidate-marker.json'))
assert marker.is_relative_to(profile)
marker.write_text('QA only', encoding='utf-8')
assert not (root / 'data' / marker.name).exists()
result.write_text(json.dumps({'profile_isolated': True, 'marker_isolated': True}), encoding='utf-8')
'''
    completed = subprocess.run([sys.executable, '-c', code, str(root), str(result)],
                               cwd=tmp_path, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(result.read_text(encoding='utf-8')) == {
        'profile_isolated': True, 'marker_isolated': True}
