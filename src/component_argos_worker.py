"""Standalone Argos adapter: immutable models, no Qt or installation/network API."""
import contextlib
import gc
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    from runtime_bootstrap import activate
    dll_runtime = activate()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    root = Path(request['root_dir']).resolve()
    action = request.get('action', 'translate')
    if action not in ('translate', 'probe', 'validate'):
        raise ValueError('Managed Argos does not modify models or fetch a package index')
    os.environ['CLICKNTRANSLATE_ARGOS_WORKER'] = '1'
    os.environ['ARGOS_DEVICE_TYPE'] = 'cpu'
    os.environ['ARGOS_MODEL_PROVIDER'] = 'OPENNMT'
    os.environ['ARGOS_EXPERIMENTAL_ENABLED'] = '0'
    os.environ['ARGOS_DEBUG'] = '0'
    os.environ['ARGOS_INTER_THREADS'] = '1'
    os.environ['ARGOS_INTRA_THREADS'] = str(min(4, os.cpu_count() or 1))
    with tempfile.TemporaryDirectory(prefix='clickntranslate_argos_state_', dir=request.get('work_dir')) as temporary:
        for key in ('XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME'):
            os.environ[key] = str(Path(temporary) / key.lower())
        os.environ['ARGOS_PACKAGES_DIR'] = str(Path(temporary) / 'empty-packages')
        os.environ.pop('ARGOS_TRANSLATE_PACKAGE_DIR', None)
        with contextlib.redirect_stdout(sys.stderr):
            import translater
            if not translater._ensure_argos_available():
                raise RuntimeError(translater.argos_unavailable_reason())
            package_roots = sorted(path for path in (root / 'models').glob('*') if path.is_dir())
            translater.arg_pkg.settings.package_dirs = package_roots
            translater._invalidate_argos_cache()
            if action == 'validate':
                installed = {f'{p.from_code}__{p.to_code}' for p in translater.arg_pkg.get_installed_packages()}
                if installed != set(request['directions']):
                    raise RuntimeError('Argos model metadata does not match the selected directions')
                for direction in sorted(installed):
                    source, target = direction.split('__', 1)
                    samples = {'en':'Hello, world!', 'ru':'Привет, мир!', 'ar':'مرحبا بالعالم!'}
                    result = translater._try_argos_translate_local(samples.get(source, '12345'),
                                                                  source, target, allow_install=False)
                    if not isinstance(result, str) or not result.strip():
                        raise RuntimeError('Argos recognizer failed: ' + direction)
                    translater._invalidate_argos_cache()
                    clear = getattr(translater.arg_tr.get_installed_languages, 'cache_clear', None)
                    if clear:
                        clear()
                    gc.collect()
                payload = {'validated': sorted(installed), 'error': '', 'dll_runtime':dll_runtime}
            else:
                import argos_worker
                request['allow_install'] = False
                event_path = request.get('event_path')
                def event_callback(event):
                    if event_path:
                        with open(event_path, 'a', encoding='utf-8') as output:
                            output.write(json.dumps(event, ensure_ascii=False) + '\n')
                payload = argos_worker.run_request(request, event_callback)
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'error': f'{type(error).__name__}: {error}'}))
        raise SystemExit(1)
