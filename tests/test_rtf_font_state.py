"""Actual tiny RTF files preserve font/codepage scope and Unicode text."""
import pytest

import document_parser as parser


@pytest.fixture
def read_rtf(tmp_path, monkeypatch):
    monkeypatch.setattr(parser, 'detect_language_code', lambda _text: 'und')

    def read(body):
        raw = body.encode('ascii')
        path = tmp_path / 'font-state.rtf'
        path.write_bytes(raw)
        result = parser.parse_document(path)
        assert result.size_bytes == len(raw)
        assert result.extension == '.rtf' and result.detected_language == 'und'
        result.text.encode('utf-8')
        return result.text

    return read


@pytest.mark.parametrize('hidden', [
    r'{\*\unknown\ansicpg1251 hidden}',
    r'{\info\ansicpg1251 hidden}',
    r'{\*\unknown{\fonttbl{\f0\fcharset204 Spoof;}}}',
    r'{\info{\fonttbl{\f0\fcharset204 Spoof;}}}',
    r'{\*\unknown{\*\fonttbl{\f0\fcharset204 Spoof;}}}',
    r'{\*\unknown\cpg1251\f0\fcharset204 hidden {\uc9\u945?????????}}',
], ids=['opaque-codepage', 'known-destination-codepage', 'opaque-font-table',
        'known-destination-font-table', 'nested-starred-font-table', 'nested-controls'])
def test_ignored_destinations_cannot_change_visible_font_or_default_codepage(read_rtf, hidden):
    body = r"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0\fcharset0 Arial;}}\f0 " + hidden + r"\f0 caf\'e9}"
    assert read_rtf(body) == 'café'


@pytest.mark.parametrize('destination', [r'\*\unknown', r'\info'], ids=['opaque', 'known'])
def test_ignored_codepage_cannot_replace_default_for_unlisted_body_font(read_rtf, destination):
    body = r'{\rtf1\ansi\ansicpg1252{' + destination + r"\ansicpg1251 hidden}\f0 caf\'e9}"
    assert read_rtf(body) == 'café'


def test_opaque_group_inside_real_font_table_cannot_overwrite_font_charset(read_rtf):
    body = (r"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0\fcharset0 Arial;}"
            r"{\*\unknown{\f0\fcharset204 Spoof;}}}\f0 caf\'e9}")
    assert read_rtf(body) == 'café'


def test_binary_payload_in_ignored_group_remains_structurally_skipped(read_rtf):
    binary = '}{\\'
    body = r'{\rtf1\ansi\ansicpg1252{\*\unknown\bin3 ' + binary + r"}\f0 caf\'e9}"
    assert read_rtf(body) == 'café'


@pytest.mark.parametrize('marker', [r'\fonttbl', r'\*\fonttbl'], ids=['ordinary', 'optional-star'])
def test_real_font_table_still_defines_explicit_font_encoding(read_rtf, marker):
    body = r'{\rtf1\ansi\ansicpg1252{' + marker + r"{\f0\fcharset204 Arial;}}\f0 \'cf\'f0\'e8\'e2\'e5\'f2}"
    assert read_rtf(body) == 'Привет'


@pytest.mark.parametrize('default_id', [0, 42])
@pytest.mark.parametrize('marker', [r'\fonttbl', r'\*\fonttbl'], ids=['ordinary', 'optional-star'])
def test_default_font_charset_is_used_without_explicit_body_font_switch(read_rtf, default_id, marker):
    body = (r'{\rtf1\ansi\ansicpg1252\deff' + str(default_id) + '{' + marker +
            r'{\f' + str(default_id) + r"\fcharset204 Arial;}}\'cf\'f0\'e8\'e2\'e5\'f2}")
    assert read_rtf(body) == 'Привет'


def test_default_font_declared_after_table_uses_its_codepage(read_rtf):
    body = r"{\rtf1\ansi\ansicpg1252{\fonttbl{\f0\fcharset204 Arial;}}\deff0 \'cf\'f0\'e8\'e2\'e5\'f2}"
    assert read_rtf(body) == 'Привет'


def test_default_font_can_supply_a_multibyte_codepage(read_rtf):
    body = r"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fcharset128 Gothic;}}\'93\'fa\'96\'7b\'8c\'ea}"
    assert read_rtf(body) == '日本語'


def test_explicit_font_override_and_plain_reset_preserve_their_own_text(read_rtf):
    body = (r"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fcharset204 Arial;}"
            r"{\f1\fcharset0 Roman;}}\f1 caf\'e9\plain \'cf\'f0\'e8\'e2\'e5\'f2}")
    assert read_rtf(body) == 'caféПривет'


def test_explicit_font_switch_is_restored_when_a_visible_group_ends(read_rtf):
    body = (r"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0\fcharset204 Arial;}"
            r"{\f1\fcharset0 Roman;}}{\f1 caf\'e9}\'cf\'f0\'e8\'e2\'e5\'f2}")
    assert read_rtf(body) == 'caféПривет'


def test_default_font_missing_from_table_keeps_ansi_fallback(read_rtf):
    assert read_rtf(r"{\rtf1\ansi\ansicpg1252\deff9{\fonttbl{\f0\fcharset204 Arial;}}caf\'e9}") == 'café'


@pytest.mark.parametrize('uc', [0, 1, 2])
@pytest.mark.parametrize('fallback', ['?', r"\'3f"], ids=['literal', 'hex'])
def test_signed_surrogates_and_unicode_fallback_counts_stay_lossless(read_rtf, uc, fallback):
    skipped = fallback * uc
    # At uc0 there is no fallback token separating the last control word:
    # its first space is the RTF delimiter; the second is visible text.
    delimiter = ' ' if uc == 0 else ''
    body = r'{\rtf1\ansi\uc' + str(uc) + r' A\u-10179' + skipped + r'\u-8704' + skipped + delimiter + ' Z}'
    assert read_rtf(body) == 'A😀 Z'


@pytest.mark.parametrize('newline', ['', '\r\n'], ids=['same-line', 'source-wrap'])
def test_unicode_control_word_delimiter_does_not_add_visible_spacing(read_rtf, newline):
    body = r'{\rtf1\ansi\uc0 A\u-10179' + newline + r'\u-8704 Z}'
    assert read_rtf(body) == 'A😀Z'


def test_unicode_fallback_and_font_encoding_both_restore_after_nested_group(read_rtf):
    body = (r"{\rtf1\ansi\ansicpg1252\deff0\uc1{\fonttbl{\f0\fcharset0 Roman;}"
            r"{\f1\fcharset204 Arial;}}caf\'e9{\f1\uc2\u945??\'cf\'f0\'e8\'e2\'e5\'f2}\u946?caf\'e9}")
    assert read_rtf(body) == 'caféαПриветβcafé'
