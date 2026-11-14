"""Native Argos lifecycle/translation checks in a fresh isolated QA profile."""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PROJECT), str(PROJECT / 'src')]
import component_argos as argos
from component_catalog import parse_catalog
from component_store import ComponentStore


def run(catalog_path, runtime, models, output):
    sys.argv[0] = str(output / 'main.py')
    os.environ['CLICKNTRANSLATE_COMPONENTS_DIR'] = str(output / 'store')
    os.environ['CLICKNTRANSLATE_COMPONENT_CHANNEL'] = 'preview'
    os.environ.pop('CLICKNTRANSLATE_ARGOS_WORKER', None)
    catalog = parse_catalog(catalog_path.read_bytes())
    store = ComponentStore(output / 'store')
    downloads = []
    files = {path.name:path for path in models.glob('*.argosmodel')}
    files[runtime.name] = runtime
    def download(url, destination):
        downloads.append(url)
        shutil.copyfile(files[url.rsplit('/', 1)[1]], destination)
    def install(**kwargs):
        return argos.install(download, root=store.root, channel='preview',
                             catalog_loader=lambda _:catalog, **kwargs)
    started = time.perf_counter()
    first = install(pairs=[('en','ru'), ('ru','en')])
    assert len(downloads) == 3
    install(pairs=[('en','ar'), ('ar','en')])
    assert len(downloads) == 5
    newer = copy.deepcopy(catalog['bundles'][0])
    newer.update(id='argos-lifecycle-r2', revision=2)
    catalog['bundles'].append(newer)
    updated = install()
    native_validation = argos.validate(updated['folder'], updated['receipt'])
    assert native_validation['dll_runtime'] == dict.fromkeys(
        ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'), 'bundled')
    assert updated['receipt']['languages'] == ['ar__en', 'en__ar', 'en__ru', 'ru__en']
    assert len(downloads) == 5
    store.rollback(argos.COMPONENT, argos.validate, catalog)
    assert store.active(argos.COMPONENT)['receipt']['revision'] == 1
    updated = install()
    import translater
    assert translater.preload_argos_runtime()
    assert translater.argos_runtime_available()
    samples = [('en','ru','Hello, world!'), ('ru','en','Привет, мир!'),
               ('en','ar','Hello, world!'), ('ar','en','مرحبا بالعالم!'),
               ('ru','ar','Привет, мир!'), ('ar','ru','مرحبا بالعالم!')]
    translated = []
    for source, target, text in samples:
        before = time.perf_counter()
        result = translater._try_argos_translate(text, source, target, allow_install=False)
        assert result and result.strip(), (source, target)
        translated.append({'source':source, 'target':target, 'text':text, 'result':result,
                           'seconds':round(time.perf_counter()-before, 2)})
    partials = []
    short = translater._try_argos_translate('Hello, world!\n\nThank you.', 'en', 'ru',
        allow_install=False, partial_callback=lambda text, done, total: partials.append((text, done, total)))
    assert short and not partials  # one request returns directly, without partial events
    long_text = 'Hello, world! Thank you. ' * 100 + '\n\nThe end.'
    streamed = translater._try_argos_translate(long_text, 'en', 'ru',
        allow_install=False, partial_callback=lambda text, done, total: partials.append((text, done, total)))
    assert partials and partials[-1][0] == streamed
    loaded = [name for name in ('ctranslate2','sentencepiece','torch','spacy') if name in sys.modules]
    assert not loaded, loaded
    def offline(*_):
        raise AssertionError('Deletion contacted a metadata/artifact server')
    removed = argos.install(offline, remove_pairs=[('ar','en')], root=store.root, catalog_loader=offline)
    assert 'ar__en' not in removed['receipt']['languages']
    assert not translater.argos_pair_installed('ar', 'en')
    store.rollback(argos.COMPONENT, argos.validate, catalog)
    assert translater.argos_pair_installed('ar','en')
    # Abort a real validator child after preparation but before activation.
    active = store.active(argos.COMPONENT)
    original = argos.validate
    validating = []
    def canceled():
        if validating:
            raise InterruptedError('QA cancellation')
    def validate_cancel(folder, receipt, check_cancel=lambda: None):
        validating.append(True)
        return original(folder, receipt, check_cancel)
    argos.validate = validate_cancel
    newer = copy.deepcopy(newer)
    newer.update(id='argos-cancel-qa-r3', revision=3)
    catalog['bundles'].append(newer)
    try:
        try:
            install(check_cancel=canceled)
        except InterruptedError:
            pass
        else:
            raise AssertionError('Cancellation was ignored')
    finally:
        argos.validate = original
    assert store.active(argos.COMPONENT)['folder'] == active['folder']
    report = {'first_generation':first['receipt']['generation'], 'artifact_downloads':len(downloads),
        'additional_update_downloads':len(downloads)-5, 'language_addition':'passed',
        'runtime_update_preserves_directions':'passed', 'offline_removal':'passed',
        'rollback':'passed', 'validator_cancellation_preserves_active':'passed',
        'streaming_translation':'passed', 'native_modules_in_parent':loaded,
        'runtime_sha256':active['receipt']['files'][0]['sha256'],
        'translations':translated, 'seconds':round(time.perf_counter()-started, 2),
        'runtime_source':'local candidate', 'application_build':False}
    report['dll_runtime'] = native_validation['dll_runtime']
    (output / 'verification.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key != 'translations'}))


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if 'ClicknTranslate-QA' not in output.parts or output.exists():
        parser.error('Use a fresh output directory below ClicknTranslate-QA')
    output.mkdir(parents=True)
    run(args.catalog, args.runtime, args.models, output)
