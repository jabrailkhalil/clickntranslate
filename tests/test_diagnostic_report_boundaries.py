"""Actual diagnostic ZIPs use only synthetic profiles, logs and credentials."""
import builtins
import json
import os
from pathlib import Path
import zipfile

import pytest

import diagnostics
import provider_secrets


@pytest.fixture
def report_sources(tmp_path, monkeypatch):
    root, temporary = tmp_path / 'application', tmp_path / 'native-logs'
    data = root / 'data'
    data.mkdir(parents=True)
    temporary.mkdir()
    (data / 'config.json').write_text('{"interface_language":"en"}', encoding='utf-8')
    monkeypatch.setattr(diagnostics, '_portable_root', lambda: root)
    monkeypatch.setattr(diagnostics.tempfile, 'gettempdir', lambda: str(temporary))
    monkeypatch.setattr(diagnostics, '_environment_report', lambda *_: {'fixture': True})
    monkeypatch.setattr(diagnostics, '_redactor', lambda: ((str(root), '<fixture-root>'),))
    monkeypatch.setattr(provider_secrets, '_SESSION', {})  # old errors need no live key/vault
    return root, temporary, tmp_path / 'reports'


@pytest.mark.parametrize('field', ['Authorization', 'x-api-key', 'api_key'])
@pytest.mark.parametrize('depth', [0, 1, 2])
def test_report_redacts_credentials_in_nested_json_and_preserves_valid_envelopes(report_sources, field, depth):
    _, temporary, output = report_sources
    secret = 'synthetic-old-key-a19e30594b744fb9'
    payload = {field: ('Bearer ' if field == 'Authorization' else '') + secret,
               'request_id': 'ordinary-error-metadata'}
    for _ in range(depth):
        payload = {'provider_error': json.dumps(payload, ensure_ascii=False)}
    log = temporary / 'clickntranslate_launcher.log'
    log.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    report = diagnostics.create_bug_report(output, runtime=payload)
    with zipfile.ZipFile(report) as archive:
        for name in ('runtime.json', 'logs/clickntranslate_launcher.log'):
            text = archive.read(name).decode('utf-8')
            assert secret not in text
            decoded = json.loads(text)
            for _ in range(depth):
                decoded = json.loads(decoded['provider_error'])
            assert decoded[field] in ('<redacted>', 'Bearer <redacted>')
            assert decoded['request_id'] == 'ordinary-error-metadata'


@pytest.mark.parametrize('secret', [
    r'old-private-left\old-private-right',
    'old-private-left;old-private-right}',
    'old-private-left"old-private-right',
    'old-private-left old-private-right',
    'old-private-left-old-private-right' + '\\',
])
@pytest.mark.parametrize('depth', [0, 1, 2])
def test_quoted_credentials_are_removed_as_whole_values(report_sources, secret, depth):
    _, temporary, output = report_sources
    payload = {'x-api-key': secret, 'request_id': 'ordinary-error-metadata'}
    for _ in range(depth):
        payload = {'provider_error': json.dumps(payload, ensure_ascii=False)}
    (temporary / 'clickntranslate_launcher.log').write_text(json.dumps(payload), encoding='utf-8')
    report = diagnostics.create_bug_report(output, runtime=payload)
    with zipfile.ZipFile(report) as archive:
        for name in ('runtime.json', 'logs/clickntranslate_launcher.log'):
            text = archive.read(name).decode('utf-8')
            assert 'old-private-left' not in text
            assert 'old-private-right' not in text
            decoded = json.loads(text)
            for _ in range(depth):
                decoded = json.loads(decoded['provider_error'])
            assert decoded == {'x-api-key': '<redacted>', 'request_id': 'ordinary-error-metadata'}


@pytest.mark.parametrize('prefix', ['x-api-key: ', 'Authorization: Bearer ', 'api_key='])
def test_unquoted_header_keeps_redacting_backslashes_in_the_token(report_sources, prefix):
    _, temporary, output = report_sources
    error = prefix + r'old-private-left\old-private-right'
    (temporary / 'clickntranslate_launcher.log').write_text(error, encoding='utf-8')
    report = diagnostics.create_bug_report(output, runtime={'failure': error})
    with zipfile.ZipFile(report) as archive:
        for name in ('runtime.json', 'logs/clickntranslate_launcher.log'):
            text = archive.read(name).decode('utf-8')
            assert 'old-private-left' not in text
            assert 'old-private-right' not in text
        assert json.loads(archive.read('runtime.json')) == {'failure': prefix + '<redacted>'}
        assert archive.read('logs/clickntranslate_launcher.log').decode('utf-8') == prefix + '<redacted>'


@pytest.mark.parametrize('depth', [0, 1, 2])
def test_quoted_header_inside_an_error_string_keeps_its_json_envelopes(report_sources, depth):
    _, temporary, output = report_sources
    payload = {'message': r'x-api-key: "old-private-left\old-private-right"',
               'request_id': 'ordinary-error-metadata'}
    for _ in range(depth):
        payload = {'provider_error': json.dumps(payload)}
    (temporary / 'clickntranslate_launcher.log').write_text(json.dumps(payload), encoding='utf-8')
    report = diagnostics.create_bug_report(output, runtime=payload)
    with zipfile.ZipFile(report) as archive:
        for name in ('runtime.json', 'logs/clickntranslate_launcher.log'):
            text = archive.read(name).decode('utf-8')
            assert 'old-private-left' not in text and 'old-private-right' not in text
            decoded = json.loads(text)
            for _ in range(depth):
                decoded = json.loads(decoded['provider_error'])
            assert decoded == {'message': 'x-api-key: "<redacted>"',
                               'request_id': 'ordinary-error-metadata'}


@pytest.mark.parametrize('prefix', ['Authorization: ', 'x-api-key: ', 'api_key=', 'password='])
@pytest.mark.parametrize('quote', ['"', "'"])
@pytest.mark.parametrize('bearer_outside', [False, True])
@pytest.mark.parametrize('depth', [0, 1, 2])
@pytest.mark.parametrize('secret', [
    r'prefix_unique_token\suffix_unique_token',
    'prefix_unique_token;suffix_unique_token}',
    'prefix_unique_token"suffix_unique_token',
    "prefix_unique_token'suffix_unique_token",
    'prefix_unique_token suffix_unique_token',
    'prefix_unique_token-suffix_unique_token' + '\\',
])
def test_header_composition_matrix_keeps_credentials_private_and_metadata_valid(
        report_sources, prefix, quote, bearer_outside, depth, secret):
    escaped = secret.replace('\\', '\\\\').replace(quote, '\\' + quote)
    message = (prefix + ('Bearer ' if bearer_outside else '') + quote
               + ('' if bearer_outside else 'Bearer ') + escaped + quote)
    payload = {'message': message, 'request_id': 'ordinary-error-metadata', 'http_status': 401}
    for _ in range(depth):
        payload = {'provider_error': json.dumps(payload)}
    text = diagnostics._redact(json.dumps(payload))
    assert 'prefix_unique_token' not in text and 'suffix_unique_token' not in text
    decoded = json.loads(text)
    for _ in range(depth):
        decoded = json.loads(decoded['provider_error'])
    assert decoded == {'message': prefix + ('Bearer ' if bearer_outside else '')
                      + quote + '<redacted>' + quote,
                       'request_id': 'ordinary-error-metadata', 'http_status': 401}


def test_json_literal_depth_budget_fails_closed_and_keeps_outer_metadata(report_sources):
    payload = {'provider_error': json.dumps({'message': 'x-api-key: "prefix_unique_token suffix_unique_token"'}),
               'request_id': 'ordinary-error-metadata'}
    # Enter the final allowed layer without allocating exponentially escaped
    # input just to reach this parser resource boundary.
    text = diagnostics._redact_credentials(json.dumps(payload), depth=32)
    assert 'prefix_unique_token' not in text and 'suffix_unique_token' not in text
    assert json.loads(text) == {'provider_error': '<redacted>',
                               'request_id': 'ordinary-error-metadata'}


def test_truncated_escaped_log_does_not_restart_a_json_literal_at_every_quote(report_sources):
    noise = r'\"' * (3 * 1024 * 1024 // 2)
    text = noise + ' x-api-key: "prefix_unique_token suffix_unique_token'
    redacted = diagnostics._redact(text)
    assert redacted == noise + ' x-api-key: "<redacted>'


def test_malformed_json_escape_does_not_prevent_credential_removal(report_sources):
    text = r'{"x-api-key":"prefix_unique_token\qsuffix_unique_token","request_id":"ordinary-error-metadata"}'
    redacted = diagnostics._redact(text)
    assert 'prefix_unique_token' not in redacted and 'suffix_unique_token' not in redacted
    assert json.loads(redacted) == {'x-api-key': '<redacted>', 'request_id': 'ordinary-error-metadata'}


@pytest.mark.parametrize('codepoint', [0xd800, 0xdfff], ids=['high-surrogate', 'low-surrogate'])
@pytest.mark.parametrize('depth', [0, 1, 2])
def test_changed_json_literal_keeps_surrogate_metadata_escaped(report_sources, codepoint, depth):
    metadata = 'ordinary-error-metadata-' + chr(codepoint)
    payload = {'message': 'x-api-key: prefix_unique_token-suffix_unique_token; ' + metadata,
               'request_id': metadata}
    for _ in range(depth):
        payload = {'provider_error': json.dumps(payload)}
    redacted = diagnostics._redact(json.dumps(payload))
    redacted.encode('utf-8')
    assert 'prefix_unique_token' not in redacted and 'suffix_unique_token' not in redacted
    decoded = json.loads(redacted)
    for _ in range(depth):
        decoded = json.loads(decoded['provider_error'])
    assert decoded == {'message': 'x-api-key: <redacted>; ' + metadata, 'request_id': metadata}


@pytest.mark.parametrize('codepoint', [0xd800, 0xdfff], ids=['high-surrogate', 'low-surrogate'])
def test_report_writes_encoded_provider_error_with_surrogate_metadata(report_sources, codepoint):
    _, temporary, output = report_sources
    metadata = 'ordinary-error-metadata-' + chr(codepoint)
    payload = {'message': 'x-api-key: prefix_unique_token-suffix_unique_token; ' + metadata,
               'request_id': metadata}
    encoded_error = json.dumps(payload)
    (temporary / 'clickntranslate_launcher.log').write_text(encoded_error, encoding='utf-8')
    report = diagnostics.create_bug_report(output, runtime={'provider_error': encoded_error})
    with zipfile.ZipFile(report) as archive:
        decoded_log = json.loads(archive.read('logs/clickntranslate_launcher.log'))
        decoded_runtime = json.loads(json.loads(archive.read('runtime.json'))['provider_error'])
        for decoded in (decoded_log, decoded_runtime):
            assert decoded == {'message': 'x-api-key: <redacted>; ' + metadata, 'request_id': metadata}


def test_log_growth_after_tail_snapshot_cannot_exceed_the_archive_input_budget(report_sources, monkeypatch):
    _, temporary, output = report_sources
    budget = 64
    log = temporary / 'clickntranslate_launcher.log'
    log.write_bytes(b'a' * budget)
    original_open, original_tail = Path.open, diagnostics._tail
    appended = []

    class GrowingLog:
        def __init__(self, source):
            self.source = source

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.source.close()

        def __getattr__(self, name):
            return getattr(self.source, name)

        def seek(self, offset, whence=0):
            result = self.source.seek(offset, whence)
            if whence == os.SEEK_SET and not appended:
                with builtins.open(log, 'ab') as writer:
                    writer.write(b'z' * (budget * 2))
                appended.append(True)
            return result

    def changing_file(path, *args, **kwargs):
        source = original_open(path, *args, **kwargs)
        return GrowingLog(source) if path == log and args == ('rb',) else source

    monkeypatch.setattr(Path, 'open', changing_file)
    monkeypatch.setattr(diagnostics, '_tail', lambda path: original_tail(path, budget))
    report = diagnostics.create_bug_report(output)
    assert appended and log.stat().st_size == budget * 3
    with zipfile.ZipFile(report) as archive:
        assert archive.getinfo('logs/clickntranslate_launcher.log').file_size == budget


def test_a_log_removed_after_inventory_becomes_a_readable_report_entry(report_sources, monkeypatch):
    _, temporary, output = report_sources
    log = temporary / 'clickntranslate_launcher.log'
    log.write_text('synthetic log', encoding='utf-8')
    original_open = Path.open

    def disappearing_file(path, *args, **kwargs):
        if path == log and args == ('rb',):
            log.unlink()
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', disappearing_file)
    report = diagnostics.create_bug_report(output)
    with zipfile.ZipFile(report) as archive:
        assert 'Could not read log:' in archive.read('logs/clickntranslate_launcher.log').decode('utf-8')
        assert json.loads(archive.read('environment.json')) == {'fixture': True}


@pytest.mark.parametrize('depth', [0, 1, 2])
def test_report_keeps_nonsecret_metadata_and_empty_credential_fields(report_sources, depth):
    _, temporary, output = report_sources
    payload = {'request_id': 'ordinary-error-metadata', 'api_provider': 'fixture',
               'authorization': '', 'password': ''}
    for _ in range(depth):
        payload = {'provider_error': json.dumps(payload, ensure_ascii=False)}
    encoded = json.dumps(payload, ensure_ascii=False)
    (temporary / 'clickntranslate_launcher.log').write_text(encoded, encoding='utf-8')
    report = diagnostics.create_bug_report(output, runtime=payload)
    with zipfile.ZipFile(report) as archive:
        for name in ('runtime.json', 'logs/clickntranslate_launcher.log'):
            assert json.loads(archive.read(name)) == payload


@pytest.mark.parametrize('size', [0, 16, 64, 192])
def test_static_log_tail_keeps_the_existing_last_bytes(report_sources, monkeypatch, size):
    _, temporary, output = report_sources
    content = bytes(range(size))
    (temporary / 'clickntranslate_launcher.log').write_bytes(content)
    original_tail = diagnostics._tail
    monkeypatch.setattr(diagnostics, '_tail', lambda path: original_tail(path, 64))
    report = diagnostics.create_bug_report(output)
    with zipfile.ZipFile(report) as archive:
        assert archive.read('logs/clickntranslate_launcher.log') == (
            content[-64:].decode('utf-8', errors='replace').encode('utf-8'))
