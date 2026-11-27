import json
import hashlib
import zipfile
import pytest

import diagnostics


def test_bug_report_excludes_histories_document_text_and_runtime_ocr_log(tmp_path, monkeypatch):
    root = tmp_path / "ClicknTranslate"
    data = root / "data"
    logs = data / "logs"
    app = root / "app"
    logs.mkdir(parents=True)
    app.mkdir(parents=True)
    (data / "config.json").write_text(
        json.dumps({
            "interface_language": "ru",
            "ocr_engine": "Windows",
            "secret_api_key": "must-not-leak",
        }),
        encoding="utf-8",
    )
    (data / "copy_history.json").write_text('["private clipboard"]', encoding="utf-8")
    (data / "translation_history.json").write_text('["private translation"]', encoding="utf-8")
    (logs / "ocr_debug.log").write_text("recognized=private document text", encoding="utf-8")
    (app / "ClicknTranslateApp.exe").write_bytes(b"application")
    monkeypatch.setattr(diagnostics, "_portable_root", lambda: root)

    report = diagnostics.create_bug_report(tmp_path / "reports", app_version="test")

    with zipfile.ZipFile(report) as archive:
        names = set(archive.namelist())
        combined = "\n".join(
            archive.read(name).decode("utf-8", errors="replace") for name in names
        )
    assert "report.txt" in names
    assert "HOW_TO_SEND.txt" in names
    assert "environment.json" in names
    assert "safe-config.json" in names
    assert report.parent.name.startswith("ClicknTranslate-bug-report-")
    assert (report.parent / "HOW_TO_SEND.txt").is_file()
    instructions = (report.parent / "HOW_TO_SEND.txt").read_text(encoding="utf-8")
    assert "github.com/jabrailkhalil/clickntranslate/issues" in instructions
    assert "t.me/jabrail_digital" in instructions
    assert "ocr_debug.log" not in combined
    assert "must-not-leak" not in combined
    assert "private clipboard" not in combined
    assert "private translation" not in combined
    assert "private document text" not in combined
    assert "intentionally excluded" in combined


def test_frozen_metadata_missing_does_not_claim_the_worker_engine_is_uninstalled(monkeypatch):
    def missing(distribution):
        raise diagnostics.importlib.metadata.PackageNotFoundError(distribution)
    monkeypatch.setattr(diagnostics.importlib.metadata, 'version', missing)
    monkeypatch.setattr(diagnostics.sys, 'frozen', True, raising=False)
    versions = diagnostics._package_versions()
    assert versions['argostranslate'] == 'metadata unavailable in this process'
    assert versions['onnxruntime'] == 'metadata unavailable in this process'


def test_report_identifies_separate_workers_and_cpu_without_running_engines(tmp_path, monkeypatch):
    import subprocess
    root = tmp_path / 'ClicknTranslate'
    workers = root / 'app' / '_internal'
    workers.mkdir(parents=True)
    data = root / 'data'
    data.mkdir()
    (data / 'config.json').write_text('{}', encoding='utf-8')
    argos = b'Argos worker fixture'
    (workers / 'ArgosWorker.exe').write_bytes(argos)
    (workers / 'OcrWorker.exe').write_bytes(b'OCR worker fixture')
    monkeypatch.setattr(diagnostics, '_portable_root', lambda: root)
    monkeypatch.setattr(diagnostics.platform, 'processor', lambda: 'QA CPU model')
    monkeypatch.setattr(diagnostics.os, 'cpu_count', lambda: 8)
    def no_process(*args, **kwargs):
        raise AssertionError('Diagnostics must not start an OCR/translation engine')
    monkeypatch.setattr(subprocess, 'Popen', no_process)
    report = diagnostics.create_bug_report(tmp_path / 'reports', app_version='test')
    with zipfile.ZipFile(report) as archive:
        text = archive.read('report.txt').decode('utf-8')
        environment = json.loads(archive.read('environment.json'))
    assert 'argos_worker: present' in text and 'ocr_worker: present' in text
    assert hashlib.sha256(argos).hexdigest() in text
    assert environment['processor'] == 'QA CPU model'
    assert environment['cpu_count'] == 8
    assert 'separate workers' in environment['packages_scope']


@pytest.mark.parametrize('folder,suffix', [('app/_internal', '.exe'), ('_internal', ''), ('', '')],
                         ids=['windows', 'linux', 'macos'])
def test_worker_report_uses_the_actual_platform_bundle_layout(tmp_path, monkeypatch, folder, suffix):
    import platform_support
    root = tmp_path / 'bundle'
    worker_dir = root / folder
    worker_dir.mkdir(parents=True)
    for stem in ('ArgosWorker', 'OcrWorker'):
        (worker_dir / (stem + suffix)).write_bytes((stem + ' fixture').encode())
    monkeypatch.setattr(platform_support, 'EXECUTABLE_SUFFIX', suffix)
    monkeypatch.setattr(diagnostics, '_portable_root', lambda: root)
    report = diagnostics.create_bug_report(tmp_path / 'reports', data_dir=root/'no-data')
    with zipfile.ZipFile(report) as archive:
        text = archive.read('report.txt').decode('utf-8')
    assert 'argos_worker: present' in text
    assert 'ocr_worker: present' in text
