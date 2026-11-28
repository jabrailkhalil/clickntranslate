import json
import subprocess
from types import SimpleNamespace

import pytest

from tools import run_ci_tests


def test_partitions_cover_every_file_once_in_deterministic_order():
    files = [f'test_{index:03}.py' for index in range(111)]
    parts = run_ci_tests.partition_files(list(reversed(files)), 2)
    assert [len(part) for part in parts] == [56, 55]
    assert sorted(name for part in parts for name in part) == files
    assert parts == run_ci_tests.partition_files(files, 2)
    assert all(part == sorted(part) for part in parts)


def test_dominant_ui_suites_get_separate_runners_and_new_files_are_included():
    heavy = ['tests/test_engine_background_jobs.py', 'tests/test_engine_center_stationary_layout.py',
             'tests/test_guide_setup.py']
    files = heavy + [f'tests/test_new_{n:02}.py' for n in range(24)]
    parts = run_ci_tests.partition_files(files, 3)
    assert all(len(set(part).intersection(heavy)) == 1 for part in parts)
    assert sorted(name for part in parts for name in part) == sorted(files)


def test_every_requested_runner_receives_work_when_there_are_enough_files():
    files = [f'tests/test_{n}.py' for n in range(7)]
    parts = run_ci_tests.partition_files(files, 6)
    assert len(parts) == 6 and all(parts)


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


def test_matrix_runs_each_file_only_in_its_assigned_part(tmp_path, monkeypatch):
    files = [f'test_{index}.py' for index in range(5)]
    partitions = run_ci_tests.partition_files(files, 2)
    commands = []

    def record_command(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_ci_tests.subprocess, 'run', record_command)

    for number, expected in enumerate(partitions, 1):
        output = tmp_path / f'job-{number}'
        assert run_ci_tests.run_partitions(partitions, output, 600, selected_part=number) == 0
        assert json.loads((output / 'plan.json').read_text()) == partitions
        assert commands[-1][-len(expected):] == expected
        assert str(output / f'part-{number}') in commands[-1]
    assert len(commands) == len(partitions)


@pytest.mark.parametrize('number', [0, 3])
def test_unknown_part_cannot_return_an_empty_success(tmp_path, number):
    with pytest.raises(ValueError, match='part must be between 1 and 2'):
        run_ci_tests.run_partitions([['a'], ['b']], tmp_path, 600, selected_part=number)


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
