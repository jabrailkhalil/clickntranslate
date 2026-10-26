"""Trusted native Hy-MT transactions and cancellable, local-only inference."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from component_catalog import (ComponentError, choose_bundle, component_store_path,
                               runtime_command, safe_relative, trusted_catalog)
from component_runtime import worker_environment
from component_store import ComponentStore, file_digest

COMPONENT = 'translation.hymt'


def legacy_disabled(root=None):
    return (Path(root or component_store_path())/'hymt-legacy-disabled').exists()


def remove(root=None):
    store = ComponentStore(root or component_store_path())
    # Explicit uninstall must not unexpectedly resurrect the preserved legacy
    # installation. Keep its original files, but disable automatic fallback.
    store.root.mkdir(parents=True, exist_ok=True)
    (store.root/'hymt-legacy-disabled').touch()
    store.remove(COMPONENT)


def runtime_info(folder, receipt):
    folder = Path(folder)
    model = folder / safe_relative(receipt.get('model'))
    if not model.is_file():
        raise ComponentError('installed_component_damaged', 'Hy-MT model')
    return {'root':str(folder), 'model':str(model), 'runner':runtime_command(folder, receipt)[0]}


def cache_identity(receipt):
    # Generation UUIDs change on reinstall/rollback; identical approved bytes
    # should reuse their cache. New runtimes/models must not reuse old output.
    import hashlib
    plan = json.dumps(receipt['files'], sort_keys=True, separators=(',', ':'))
    return 'hymt:prompt-v2:' + hashlib.sha256(plan.encode('utf-8')).hexdigest()[:20]


def _run(command, *, cwd, check_cancel, timeout):
    """Wait without pipe deadlocks; always reap the child before releasing files."""
    with tempfile.TemporaryDirectory(prefix='clickntranslate_hymt_process_') as temporary:
        work = Path(temporary)
        environment = worker_environment()
        for name in tuple(environment):
            if name.startswith('LLAMA_ARG_'):
                environment.pop(name)
        environment['PATH'] = str(cwd) + os.pathsep + environment.get('PATH', '')
        environment['LLAMA_CACHE'] = str(work / 'cache')
        check_cancel()
        with (work/'stdout.txt').open('w', encoding='utf-8') as stdout, \
                (work/'stderr.txt').open('w', encoding='utf-8') as stderr:
            process = subprocess.Popen(command, cwd=str(cwd), env=environment,
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    check_cancel()
                    if time.monotonic() >= deadline:
                        raise ComponentError('inference_timeout', 'Hy-MT')
                    time.sleep(.05)
                check_cancel()
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
        def read(name):
            path = work/name
            if path.stat().st_size > 4*1024**2:
                raise ComponentError('inference_failed', 'Hy-MT response too large')
            return path.read_text(encoding='utf-8', errors='replace')
        return subprocess.CompletedProcess(command, process.returncode, read('stdout.txt'), read('stderr.txt'))


def translate(folder, receipt, text, source, target, *, check_cancel=lambda:None, max_tokens=None):
    from translater import _build_hymt_prompt, _clean_hymt_output
    runtime = runtime_info(folder, receipt)
    prompt = _build_hymt_prompt(text, source, target)
    tokens = max_tokens or max(96, min(2048, int(len(text)*1.6)+64))
    with tempfile.TemporaryDirectory(prefix='clickntranslate_hymt_prompt_') as temporary:
        path = Path(temporary)/'prompt.txt'
        path.write_text(prompt, encoding='utf-8')
        command = [runtime['runner'], '-m', runtime['model'], '-f', str(path), '-n', str(tokens),
            '-c', '4096', '-t', str(min(4, os.cpu_count() or 1)), '-ngl', '0',
            '--temp', '0', '--top-p', '1', '--no-display-prompt', '--single-turn',
            '--no-warmup', '--no-perf', '--no-show-timings', '--log-disable', '--simple-io', '--no-escape']
        result = _run(command, cwd=Path(runtime['runner']).parent, check_cancel=check_cancel, timeout=300)
    if result.returncode:
        raise ComponentError('inference_failed', 'Hy-MT exit ' + str(result.returncode))
    translated = _clean_hymt_output(result.stdout, prompt)
    if not translated:
        raise ComponentError('inference_failed', 'Hy-MT empty result')
    return translated


def validate(folder, receipt, check_cancel=lambda:None):
    info = runtime_info(folder, receipt)
    with Path(info['model']).open('rb') as model:
        if model.read(4) != b'GGUF':
            raise ComponentError('validation_failed', 'Hy-MT GGUF header')
    result = _run([info['runner'], '--version'], cwd=Path(info['runner']).parent,
                  check_cancel=check_cancel, timeout=30)
    version = result.stdout + result.stderr
    if result.returncode or not receipt.get('runner_build') or receipt['runner_build'] not in version:
        raise ComponentError('validation_failed', 'llama.cpp version')
    results = []
    for source, target, text in [('en','ru','Hello, world!'), ('ru','en','Привет, мир!'),
                                  ('en','ar','Hello, world!')]:
        check_cancel()
        result = translate(folder, receipt, text, source, target, check_cancel=check_cancel, max_tokens=64)
        if result == text:
            raise ComponentError('validation_failed', 'Hy-MT returned untranslated probe')
        results.append({'source':source,'target':target,'result':result})
    return {'runner_build':receipt['runner_build'], 'inference':results, 'error':''}


def install(download, *, root=None, channel=None, legacy_model=None, check_cancel=lambda:None,
            progress=lambda *_:None, catalog_loader=trusted_catalog):
    from app_version import APP_VERSION
    store = ComponentStore(root or component_store_path())
    with store.lock():
        check_cancel()
        catalog = catalog_loader(store.root)
        try:
            old = store.active(COMPONENT)
        except ComponentError:
            old = None
        bundle = choose_bundle(catalog, COMPONENT, APP_VERSION,
            channel=channel or os.environ.get('CLICKNTRANSLATE_COMPONENT_CHANNEL','stable'),
            languages=old['receipt']['languages'] if old else ())
        model = next((item for item in bundle['files'] if item['destination'] == bundle.get('model')), None)
        if not model or model['kind'] != 'file':
            raise ComponentError('invalid_catalog', 'Hy-MT model plan')
        # Adopt a verified legacy model into the cache without modifying its
        # original file. Never silently replace a custom model during migration.
        if not old and legacy_model and not legacy_disabled(store.root):
            source = Path(legacy_model)
            expected = catalog['artifacts'][model['sha256']]
            if source.stat().st_size != expected['size'] or file_digest(source) != model['sha256']:
                raise ComponentError('custom_model_not_approved', 'Hy-MT')
            store.obtain(model['sha256'], expected, lambda _, path: _copy(source, path, check_cancel), check_cancel)
        return store.install(catalog, bundle, download,
            lambda folder, receipt:validate(folder, receipt, check_cancel), check_cancel, progress)


def _copy(source, destination, check_cancel):
    with source.open('rb') as original, open(destination,'wb') as output:
        while True:
            check_cancel()
            block = original.read(1024*1024)
            if not block:
                break
            output.write(block)
