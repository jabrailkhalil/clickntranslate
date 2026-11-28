"""History actions use generated text and a temporary portable directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tracemalloc
from types import SimpleNamespace

import pytest

import history_storage
import main
import ocr


@pytest.fixture(params=['copy', 'translation'])
def history(request, tmp_path, monkeypatch):
    config = {'copy_history': True, 'history': True, 'notifications': False}
    path = tmp_path / (request.param + '.json')
    if request.param == 'copy':
        monkeypatch.setattr(main, 'get_cached_config', lambda: config)
        monkeypatch.setattr(main, 'get_data_file', lambda _name: str(path))
        save = main.save_copy_history
        key = 'text'
    else:
        monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: config)
        monkeypatch.setattr(ocr, 'get_data_file', lambda _name: str(path))
        save = lambda text: ocr.save_translation_history(text, 'result ' + text, 'fr')
        key = 'original'
    return SimpleNamespace(config=config, path=path, save=save, key=key)


def test_saved_actions_keep_submission_order_and_finish_at_interpreter_exit(history, monkeypatch):
    first_entered, first_release = threading.Event(), threading.Event()
    done = {name: threading.Event() for name in ('first', 'second')}
    writers = []
    append = history_storage.append_record

    def controlled_append(path, record, **kwargs):
        name = record[history.key]
        writers.append(threading.current_thread())
        if name == 'first':
            first_entered.set()
            assert first_release.wait(4)
        append(path, record, **kwargs)
        done[name].set()

    monkeypatch.setattr(history_storage, 'append_record', controlled_append)
    history.save('first')
    try:
        assert first_entered.wait(2)
        history.save('second')
        done['second'].wait(.12)
    finally:
        first_release.set()
    assert all(event.wait(2) for event in done.values())
    for writer in writers:
        writer.join(2)
    records = history_storage.read_records(history.path)
    assert [r[history.key] for r in records] == ['first', 'second']
    assert len(set(writers)) == 1
    assert not writers[0].daemon and not writers[0].is_alive()


def test_enabling_history_does_not_retroactively_store_an_action(history, monkeypatch):
    pending = []
    monkeypatch.setattr(threading, 'Thread', lambda target, args=(), **_:
                        SimpleNamespace(start=lambda: pending.append(lambda: target(*args))))
    history.config.update(copy_history=False, history=False)
    history.save('while disabled')
    history.config.update(copy_history=True, history=True)
    for job in pending:
        job()
    assert history_storage.read_records(history.path) == []


def test_cleared_history_cannot_be_restored_by_an_older_queued_save(history, monkeypatch):
    from settings_window import SettingsWindow
    pending = []
    monkeypatch.setattr(threading, 'Thread', lambda target, args=(), **_:
                        SimpleNamespace(start=lambda: pending.append(lambda: target(*args))))
    history_storage.append_record(history.path, {history.key: 'already on disk'})
    history.save('submitted before Clear')
    SettingsWindow._write_history_records(history.path, [])
    history.save('submitted after Clear')
    for job in pending:
        job()
    assert [record[history.key] for record in history_storage.read_records(history.path)] == ['submitted after Clear']


def test_a_failed_clear_preserves_both_saved_and_still_queued_actions(history, monkeypatch):
    from settings_window import SettingsWindow
    pending = []
    monkeypatch.setattr(threading, 'Thread', lambda target, args=(), **_:
                        SimpleNamespace(start=lambda: pending.append(lambda: target(*args))))
    history_storage.append_record(history.path, {history.key: 'already on disk'})
    history.save('pending action')
    with monkeypatch.context() as fail:
        def refuse(*args, **kwargs):
            raise PermissionError('temporary save failure')
        fail.setattr(history_storage, 'write_json', refuse)
        with pytest.raises(PermissionError):
            SettingsWindow._write_history_records(history.path, [])
    for job in pending:
        job()
    assert [record[history.key] for record in history_storage.read_records(history.path)] == [
        'already on disk', 'pending action']


def test_a_burst_of_saves_does_not_multiply_the_shutdown_wait_for_one_busy_file(history, monkeypatch):
    pending, now = [], [0.0]
    monkeypatch.setattr(threading, 'Thread', lambda target, args=(), **_:
                        SimpleNamespace(start=lambda: pending.append(lambda: target(*args))))
    monkeypatch.setattr(history_storage, 'time', SimpleNamespace(
        monotonic=lambda: now[0], sleep=lambda delay: now.__setitem__(0, now[0] + delay)))
    monkeypatch.setattr(history_storage, '_LOCK_TIMEOUT', .1)
    history.path.write_text('[]', encoding='utf-8')
    with history.path.with_suffix('.json.lock').open('w+b') as locked:
        locked.write(b'0')
        locked.flush()
        locked.seek(0)
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(locked.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(locked, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for index in range(6):
            history.save(str(index))
        for job in pending:
            job()
    assert history_storage.read_records(history.path) == []
    assert now[0] <= .101


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-16', 'utf-32'])
def test_standard_unicode_history_encodings_survive_the_next_save(tmp_path, encoding):
    path = tmp_path / 'portable-history.json'
    before = [{'text': 'مرحبا 🌍'}]
    path.write_text(json.dumps(before, ensure_ascii=False), encoding=encoding)
    history_storage.append_record(path, {'text': 'Привет'})
    assert history_storage.read_records(path) == before + [{'text': 'Привет'}]


def test_an_external_history_lock_has_a_deadline_and_the_next_save_recovers(tmp_path, monkeypatch):
    path = tmp_path / 'history.json'
    path.write_text('[{"text":"prior"}]', encoding='utf-8')
    lock = tmp_path / 'history.json.lock'
    lock.write_bytes(b'0')
    monkeypatch.setattr(history_storage, '_LOCK_TIMEOUT', .06)
    with lock.open('r+b') as other_process:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(other_process.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(other_process, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            history_storage.append_record(path, {'text': 'busy'})
        assert time.monotonic() - started < 1.0
        assert history_storage.read_records(path) == [{'text': 'prior'}]
    history_storage.append_record(path, {'text': 'next'})
    assert history_storage.read_records(path) == [{'text': 'prior'}, {'text': 'next'}]


def test_thread_start_failure_does_not_write_history_on_the_callers_thread(history, monkeypatch, caplog):
    def fail_to_start():
        raise RuntimeError('test thread unavailable')
    monkeypatch.setattr(threading, 'Thread', lambda **_: SimpleNamespace(start=fail_to_start))
    history.save('private test message')
    assert not history.path.exists()
    assert 'history' in caplog.text.lower() and 'private test message' not in caplog.text


def test_a_slow_healthy_volume_retains_two_large_documents_and_a_burst_of_small_writes(tmp_path, monkeypatch):
    pending = []
    path = tmp_path / 'translation_history.json'
    monkeypatch.setattr(threading, 'Thread', lambda target, **_: SimpleNamespace(start=lambda: pending.append(target)))
    monkeypatch.setattr(ocr, 'get_cached_ocr_config', lambda: {'history': True})
    monkeypatch.setattr(ocr, 'get_data_file', lambda _name: str(path))
    large = ['A' * 1_100_000, 'B' * 1_100_000]
    for text in large:
        ocr.save_translation_history(text, 'finished', 'fr')
    delivered = []
    for index in range(75):
        history_storage.queue_write(lambda value, **_: delivered.append(value), str(index))
    assert len(pending) == 1
    pending.pop()()
    assert [record['original'] for record in history_storage.read_records(path)] == large
    assert delivered == [str(i) for i in range(75)]


def test_saving_a_multilingual_history_does_not_allocate_another_whole_document(tmp_path):
    from atomic_storage import write_json
    path = tmp_path / 'translation_history.json'
    records = [{'original': 'A' * 2300 + str(i), 'translated': str(i), 'language': 'fr'} for i in range(500)]
    records[-1]['translated'] = '🌍'
    already_tracing = tracemalloc.is_tracing()
    if not already_tracing:
        tracemalloc.start()
    try:
        before, previous_peak = tracemalloc.get_traced_memory()
        write_json(path, records, indent=4)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        if not already_tracing:
            tracemalloc.stop()
    if not already_tracing or peak > previous_peak:
        assert peak - before < path.stat().st_size
    assert history_storage.read_records(path) == records


def test_failed_history_serialization_does_not_replace_the_previous_file(tmp_path):
    path = tmp_path / 'translation_history.json'
    history_storage.append_record(path, {'text': 'Обработано'})
    previous = path.read_bytes()
    with pytest.raises(TypeError):
        history_storage.append_record(path, {'text': object()})
    assert path.read_bytes() == previous
    assert not list(tmp_path.glob('.cnt-save-*.tmp'))


def test_overlapping_submissions_write_in_the_order_assigned_at_admission(monkeypatch):
    first_admitted, release, second_started, second_done = (threading.Event() for _ in range(4))
    written = []
    finished = threading.Event()
    submit = history_storage._writer.submit

    def gated_submit(job):
        if threading.current_thread() is first:
            first_admitted.set()
            assert release.wait(3)
        return submit(job)

    def write(text, *, submitted):
        written.append((submitted.order, text))
        if len(written) == 2:
            finished.set()

    def submit_second():
        second_started.set()
        history_storage.queue_write(write, 'second')
        second_done.set()

    monkeypatch.setattr(history_storage._writer, 'submit', gated_submit)
    first = threading.Thread(target=lambda: history_storage.queue_write(write, 'first'))
    second = threading.Thread(target=submit_second)
    first.start()
    try:
        assert first_admitted.wait(2)
        second.start()
        assert second_started.wait(2)
        second_done.wait(.15)
    finally:
        release.set()
    first.join(2)
    second.join(2)
    assert finished.wait(2)
    assert written == sorted(written) and [value for _, value in written] == ['first', 'second']


def test_normal_interpreter_exit_persists_every_accepted_local_write(tmp_path):
    path = tmp_path / 'history.json'
    source = Path(history_storage.__file__).resolve().parent
    code = '''
import sys, time
from history_storage import append_record, queue_write
def save(text, *, submitted):
    time.sleep(.05)
    append_record(sys.argv[1], {'text': text}, submitted=submitted)
for text in ('first', 'second', 'last'):
    assert queue_write(save, text)
'''
    completed = subprocess.run(
        [sys.executable, '-c', code, str(path)], cwd=tmp_path,
        env=dict(os.environ, PYTHONPATH=str(source)), timeout=8, capture_output=True, text=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    assert completed.returncode == 0, completed.stderr
    assert [record['text'] for record in history_storage.read_records(path)] == ['first', 'second', 'last']
