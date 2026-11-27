"""Independent report jobs share a Desktop destination and second-resolution stamp."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
import zipfile

import pytest
import diagnostics


@pytest.fixture
def reports(tmp_path, monkeypatch):
    destination = tmp_path / 'reports with spaces'
    data = tmp_path / 'private-profile'
    data.mkdir()
    root = tmp_path / 'synthetic-app'
    root.mkdir()
    monkeypatch.setattr(diagnostics, '_portable_root', lambda: root)
    monkeypatch.setattr(diagnostics, '_environment_report', lambda *_: {'audit': 'private fixture'})
    monkeypatch.setattr(diagnostics, '_package_versions', lambda: {})
    monkeypatch.setattr(diagnostics.platform, 'platform', lambda: 'synthetic audit platform')
    monkeypatch.setattr(diagnostics.platform, 'win32_ver', lambda: ('', '', '', ''))
    monkeypatch.setattr(diagnostics.platform, 'machine', lambda: 'synthetic')
    strftime = diagnostics.time.strftime
    stamp = '20300101-010203'
    monkeypatch.setattr(diagnostics.time, 'strftime', lambda fmt, *args:
                        stamp if fmt == '%Y%m%d-%H%M%S' else strftime(fmt, *args))
    return destination, data, stamp


def test_parallel_reports_reserve_distinct_folders_in_the_same_second(reports, monkeypatch):
    destination, data, stamp = reports
    first = destination / ('ClicknTranslate-bug-report-' + stamp)
    original_exists, original_mkdir = Path.exists, Path.mkdir
    barrier = threading.Barrier(2)
    local = threading.local()

    def exists(path):
        observed = original_exists(path)
        if path == first and not getattr(local, 'exists_probed', False):
            local.exists_probed = True
            barrier.wait(timeout=5)
        return observed

    def mkdir(path, *args, **kwargs):
        # After the fix, collide at atomic reservation itself, without a
        # preceding exists() check. Both source variants see the same race.
        if path == first and not getattr(local, 'exists_probed', False):
            local.exists_probed = True
            barrier.wait(timeout=5)
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'exists', exists)
    monkeypatch.setattr(Path, 'mkdir', mkdir)

    def create(version):
        return diagnostics.create_bug_report(destination, app_version=version, data_dir=data)

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(create, version) for version in ('audit-A', 'audit-B')]
        outcomes = []
        for job in jobs:
            try:
                outcomes.append(job.result(timeout=10))
            except Exception as error:
                outcomes.append(error)
    assert all(isinstance(item, Path) for item in outcomes), [type(item).__name__ for item in outcomes]
    assert len(set(outcomes)) == 2
    assert len({item.parent for item in outcomes}) == 2
    versions = set()
    for path in outcomes:
        with zipfile.ZipFile(path) as archive:
            report = archive.read('report.txt').decode('utf-8')
            versions.add(next(line for line in report.splitlines() if line.startswith('app_version:')))
            assert archive.testzip() is None
        assert (path.parent / 'HOW_TO_SEND.txt').is_file()
    assert versions == {'app_version: audit-A', 'app_version: audit-B'}


def test_existing_report_and_same_name_file_are_never_replaced(reports):
    destination, data, stamp = reports
    destination.mkdir()
    occupied = destination / ('ClicknTranslate-bug-report-' + stamp)
    occupied.write_bytes(b'preserve existing name')
    first = diagnostics.create_bug_report(destination, app_version='first', data_dir=data)
    first_bytes = first.read_bytes()
    second = diagnostics.create_bug_report(destination, app_version='second', data_dir=data)
    assert occupied.read_bytes() == b'preserve existing name'
    assert first.read_bytes() == first_bytes
    assert first.parent.name.endswith('-2')
    assert second.parent.name.endswith('-3')


def test_report_permission_failure_is_not_hidden_or_retried_as_a_collision(reports, monkeypatch):
    destination, data, stamp = reports
    original = Path.mkdir
    attempted = []

    def denied(path, *args, **kwargs):
        if path.parent == destination and path.name.startswith('ClicknTranslate-bug-report-'):
            attempted.append(path)
            raise PermissionError('private synthetic reservation denied')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', denied)
    with pytest.raises(PermissionError, match='synthetic reservation denied'):
        diagnostics.create_bug_report(destination, data_dir=data)
    assert attempted == [destination / ('ClicknTranslate-bug-report-' + stamp)]
