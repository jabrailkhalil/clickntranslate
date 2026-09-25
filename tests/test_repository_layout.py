"""Source reorganization must not change runtime resources or user data paths."""
from pathlib import Path
import sys

import instance_lifecycle
import portable_paths
import project_paths


ROOT = Path(__file__).resolve().parents[1]


def test_source_resources_do_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    assert project_paths.repository_root() == ROOT
    assert project_paths.source_entry() == ROOT / 'main.py'
    assert (project_paths.resource_root() / 'icons/icon.ico').is_file()
    import main
    import ocr
    import settings_window
    expected = ROOT / 'src/icons/icon.ico'
    for module in (main, ocr, settings_window):
        assert Path(module.resource_path('icons/icon.ico')) == expected


def test_frozen_resources_still_use_the_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert project_paths.resource_root() == tmp_path


def test_windows_source_data_stays_at_the_root_entry(monkeypatch):
    monkeypatch.setattr(portable_paths.platform_support, 'IS_MAC', False)
    monkeypatch.setattr(portable_paths.platform_support, 'IS_LINUX', False)
    monkeypatch.setattr(portable_paths, 'is_windows_packaged', lambda: False)
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(sys, 'argv', [str(ROOT / 'main.py')])
    assert Path(portable_paths.portable_base_dir()) == ROOT


def test_another_reorganized_source_checkout_is_recognized(tmp_path):
    checkout = tmp_path / 'checkout'
    for name in ('src/translater.py', 'src/single_instance.py', 'src/icons/icon.ico'):
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    script = checkout / 'main.py'
    process = {'exe': 'pythonw.exe', 'cmdline': ['pythonw.exe', str(script)]}
    assert instance_lifecycle.application_path(process, str(ROOT / 'main.py')) == str(script)
