"""Standalone Argos adapter: immutable models, no Qt or installation/network API."""
import contextlib
import gc
import json
import os
from pathlib import Path
import re
import sys
import tempfile


# Source-language probes, not interface strings. A new language needs meaningful
# samples before its model can be approved; translating digits cannot check it.
VALIDATION_SAMPLES = {
    'en': ('Hello, world!', 'Today the weather is good.'),
    'ru': ('Привет, мир!', 'Сегодня хорошая погода.'),
    'ar': ('مرحبا بالعالم!', 'الطقس جميل اليوم.'),
    'es': ('Hola, mundo!', 'Hoy hace buen tiempo.'),
    'de': ('Hallo, Welt!', 'Heute ist das Wetter schön.'),
    'fr': ('Bonjour le monde !', 'Il fait beau aujourd’hui.'),
    'zh': ('你好，世界！', '今天天气很好。'),
    'pt': ('Olá, mundo!', 'Hoje o tempo está bom.'),
    'it': ('Ciao, mondo!', 'Oggi il tempo è bello.'),
    'tr': ('Merhaba dünya!', 'Bugün hava güzel.'),
    'hi': ('नमस्ते दुनिया!', 'आज मौसम अच्छा है।'),
    'id': ('Halo dunia!', 'Cuaca hari ini bagus.'),
    'pl': ('Witaj, świecie!', 'Dzisiaj jest ładna pogoda.'),
    'uk': ('Привіт, світе!', 'Сьогодні гарна погода.'),
    'ja': ('こんにちは、世界！', '今日はいい天気です。'),
    'ko': ('안녕하세요, 세계!', '오늘은 날씨가 좋습니다.'),
    'nl': ('Hallo wereld!', 'Vandaag is het mooi weer.'),
}
_REPEATED_OUTPUT = re.compile(r'(.{1,64}?)\1{7,}')


def _probe_fingerprint(result, direction):
    """Reject gross decoder failures, without grading normal translation wording."""
    if not isinstance(result, str) or not result.strip():
        raise RuntimeError('Argos validation failed: empty output for ' + direction)
    if len(result) > 4096:
        raise RuntimeError('Argos validation failed: excessive output for ' + direction)
    compact = ''.join(character for character in result.casefold() if character.isalnum())
    if not compact:
        raise RuntimeError('Argos validation failed: no text for ' + direction)
    if len(compact) >= 64 and any(
        match.end() - match.start() >= len(compact) * .6
        for match in _REPEATED_OUTPUT.finditer(compact)
    ):
        raise RuntimeError('Argos validation failed: repetitive output for ' + direction)
    return compact


def _validate_models(translater, directions):
    packages = translater.arg_pkg.get_installed_packages()
    installed = {f'{package.from_code}__{package.to_code}' for package in packages}
    if installed != set(directions) or len(packages) != len(installed):
        raise RuntimeError('Argos model metadata does not match the selected directions')
    for direction in sorted(installed):
        source, target = direction.split('__', 1)
        samples = VALIDATION_SAMPLES.get(source)
        if samples is None:
            raise RuntimeError('No Argos validation samples defined for ' + source)
        outputs = []
        for sample in samples:
            result = translater._try_argos_translate_local(sample, source, target, allow_install=False)
            outputs.append(_probe_fingerprint(result, direction))
        if len(set(outputs)) != len(outputs):
            raise RuntimeError('Argos validation failed: identical output for distinct inputs in ' + direction)
        translater._invalidate_argos_cache()
        clear = getattr(translater.arg_tr.get_installed_languages, 'cache_clear', None)
        if clear:
            clear()
        gc.collect()
    return sorted(installed)


def main():
    from runtime_bootstrap import activate
    dll_runtime = activate()
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    root = Path(request['root_dir']).resolve()
    action = request.get('action', 'translate')
    if action not in ('translate', 'translate_chunks', 'probe', 'validate'):
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
        # This child owns temporary state only. Avoid platform user-data helpers
        # and GUI/macOS modules, even when importing the legacy translation API.
        import portable_paths
        portable_paths.portable_base_dir = lambda: temporary
        with contextlib.redirect_stdout(sys.stderr):
            import translater
            if not translater._ensure_argos_available():
                raise RuntimeError(translater.argos_unavailable_reason())
            package_roots = sorted(path for path in (root / 'models').glob('*') if path.is_dir())
            translater.arg_pkg.settings.package_dirs = package_roots
            translater._invalidate_argos_cache()
            if action == 'validate':
                validated = _validate_models(translater, request['directions'])
                payload = {'validated': validated, 'error': '', 'dll_runtime':dll_runtime}
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
