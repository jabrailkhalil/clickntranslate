"""An optional diagnostic file must never prevent OCR from loading."""
import logging
from pathlib import Path
from unittest import mock

import pytest

import ocr


@pytest.mark.parametrize('frozen', [False, True])
def test_logs_follow_the_data_directory_in_source_and_packaged_runs(tmp_path, monkeypatch, frozen):
    monkeypatch.setattr(ocr.sys, 'frozen', frozen, raising=False)
    monkeypatch.setattr(ocr.portable_paths, 'portable_base_dir', lambda: str(tmp_path))
    assert Path(ocr.get_log_dir()) == tmp_path / 'data/logs'
    assert (tmp_path / 'data/logs').is_dir()


@pytest.mark.parametrize('failure', ['directory', 'file'])
def test_unwritable_diagnostics_do_not_stop_ocr(tmp_path, failure):
    root = logging.Logger('isolated-ocr-test')
    with mock.patch.object(ocr.logging, 'getLogger', return_value=root), \
            mock.patch.object(ocr, 'get_log_path', return_value=str(tmp_path / 'ocr.log')) as path, \
            mock.patch.object(ocr.logging.handlers, 'RotatingFileHandler') as handler:
        (path if failure == 'directory' else handler).side_effect = PermissionError('read-only test directory')
        assert ocr._setup_ocr_diagnostics_logging() is False
        assert not root.handlers


def test_logging_can_recover_and_reopen_without_duplicate_handlers(tmp_path):
    root = logging.Logger('isolated-ocr-test')
    with mock.patch.object(ocr.logging, 'getLogger', return_value=root), \
            mock.patch.object(ocr, 'get_log_path', return_value=str(tmp_path / 'ocr.log')), \
            mock.patch.object(ocr, '_debug_log_path', None):
        try:
            assert ocr._setup_ocr_diagnostics_logging() is True
            assert ocr._setup_ocr_diagnostics_logging() is True
            assert len(root.handlers) == 1
            root.warning('first entry')
            ocr.close_ocr_diagnostics_logging()
            assert not root.handlers
            ocr.reopen_ocr_diagnostics_logging()
            root.warning('second entry')
        finally:
            ocr.close_ocr_diagnostics_logging()
    text = (tmp_path / 'ocr.log').read_text(encoding='utf-8')
    assert text.count('first entry') == text.count('second entry') == 1
