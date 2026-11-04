"""Source reorganization must not change runtime resources or user data paths."""
from pathlib import Path
import sys
import pytest

import instance_lifecycle
import portable_paths
import project_paths


ROOT = Path(__file__).resolve().parents[1]


def test_repository_root_has_only_the_five_public_entry_files():
    allowed = {'.gitattributes', '.gitignore', 'AGENTS.md', 'LICENSE', 'README.md'}
    actual = {path.name for path in ROOT.iterdir() if path.is_file() and path.name not in {'.git', '.DS_Store'}}
    assert actual <= allowed
    assert len(actual) <= 5
    for path in ('src/main.py', 'src/app_version.py', 'tools/requirements/windows.txt',
                 'tools/requirements/linux.txt', 'tools/requirements/macos.txt',
                 'tests/pytest.ini', 'docs/PRIVACY.md', 'docs/CITATION.cff'):
        assert (ROOT / path).is_file(), path


@pytest.mark.parametrize('linux', [False, True])
def test_source_entry_relocation_preserves_existing_data_and_qa_isolation(monkeypatch, tmp_path, linux):
    monkeypatch.setattr(portable_paths.platform_support, 'IS_MAC', False)
    monkeypatch.setattr(portable_paths.platform_support, 'IS_LINUX', linux)
    monkeypatch.setattr(portable_paths.platform_support, 'is_appimage', lambda: False)
    monkeypatch.setattr(portable_paths, 'is_windows_packaged', lambda: False)
    monkeypatch.delattr(sys, 'frozen', raising=False)
    monkeypatch.setattr(sys, 'argv', [str(project_paths.source_entry())])
    assert Path(portable_paths.portable_base_dir()) == ROOT
    monkeypatch.setattr(sys, 'argv', [str(tmp_path / 'main.py')])
    assert Path(portable_paths.portable_base_dir()) == tmp_path


def test_source_resources_do_not_depend_on_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delattr(sys, '_MEIPASS', raising=False)
    assert project_paths.repository_root() == ROOT
    assert project_paths.source_entry() == ROOT / 'src/main.py'
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
    monkeypatch.setattr(sys, 'argv', [str(ROOT / 'src/main.py')])
    assert Path(portable_paths.portable_base_dir()) == ROOT


@pytest.mark.parametrize('entry', ['main.py', 'src/main.py'])
def test_another_reorganized_source_checkout_is_recognized(tmp_path, entry):
    checkout = tmp_path / 'checkout'
    for name in ('src/translater.py', 'src/single_instance.py', 'src/icons/icon.ico'):
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    script = checkout / entry
    process = {'exe': 'pythonw.exe', 'cmdline': ['pythonw.exe', str(script)]}
    assert instance_lifecycle.application_path(process, str(ROOT / 'src/main.py')) == str(script)
