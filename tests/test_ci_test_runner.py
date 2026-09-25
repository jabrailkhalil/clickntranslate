import subprocess
from types import SimpleNamespace

import pytest

from tools import run_ci_tests


def test_partitions_cover_every_file_once_in_order():
    files = [f'test_{index:03}.py' for index in range(111)]
    parts = run_ci_tests.partition_files(list(reversed(files)), 2)
    assert [len(part) for part in parts] == [56, 55]
    assert [name for part in parts for name in part] == files


def test_partitions_reject_empty_input_or_invalid_count():
    with pytest.raises(ValueError):
        run_ci_tests.partition_files([], 2)
    with pytest.raises(ValueError):
        run_ci_tests.partition_files(['test_one.py'], 0)
    assert run_ci_tests.partition_files(['test_one.py'], 3) == [['test_one.py']]


def test_failed_part_does_not_skip_remaining_files(tmp_path, monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=1 if len(commands) == 1 else 0)

    monkeypatch.setattr(run_ci_tests.subprocess, 'run', fake_run)
    assert run_ci_tests.run_partitions([['test_a.py'], ['test_b.py']], tmp_path, 600) == 1
    assert [command[-1] for command in commands] == ['test_a.py', 'test_b.py']
    assert all('run_regression_tests.py' in command[1] for command in commands)


def test_timeout_is_reported_and_next_part_runs(tmp_path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_ci_tests.subprocess, 'run', fake_run)
    assert run_ci_tests.run_partitions([['test_a.py'], ['test_b.py']], tmp_path, 1) == 1
    assert len(calls) == 2
