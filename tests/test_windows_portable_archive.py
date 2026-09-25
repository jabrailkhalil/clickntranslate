import zipfile

import pytest

from release_manifest import MANIFEST, REQUIRED, write_manifest
from tools.package_windows_portable import package


def stage(tmp_path):
    root = tmp_path / 'stage'
    for relative in REQUIRED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    (root / 'data').mkdir()
    (root / 'data/settings.json').write_text('private')
    write_manifest(root, '1.8.0')
    return root


def test_archive_keeps_hidden_manifest_and_program_bytes(tmp_path):
    root = stage(tmp_path)
    output = tmp_path / 'portable.zip'
    assert package(root, output, '1.8.0') == len(REQUIRED)
    with zipfile.ZipFile(output) as archive:
        assert len(archive.infolist()) == len(REQUIRED) + 1
        manifest = archive.getinfo('ClicknTranslate/' + MANIFEST)
        assert manifest.create_system == 0
        assert manifest.external_attr & 0x02
        for info in archive.infolist():
            relative = info.filename.removeprefix('ClicknTranslate/')
            assert archive.read(info) == (root / relative).read_bytes()
            if relative != MANIFEST:
                assert not info.external_attr & 0x02


def test_archive_rejects_output_inside_stage(tmp_path):
    root = stage(tmp_path)
    with pytest.raises(ValueError, match='outside'):
        package(root, root / 'portable.zip', '1.8.0')


def test_archive_rejects_damaged_stage(tmp_path):
    root = stage(tmp_path)
    (root / 'clickntranslate.exe').write_bytes(b'damaged')
    with pytest.raises(ValueError, match='damaged'):
        package(root, tmp_path / 'portable.zip', '1.8.0')
