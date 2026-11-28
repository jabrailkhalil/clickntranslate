"""Malformed files and monitor changes must not corrupt saved capture layouts."""
import copy
import json
import random
from types import SimpleNamespace

import pytest
from PyQt5 import QtCore

from dynamic_templates import TemplateStore, encode_rect, decode_rect, validate_template


def template():
    area = {'screen': 'screen', 'rect': [.1, .2, .3, .4]}
    return {'name': 'Subtitles', 'source_language': 'en', 'target_language': 'ru',
            'pairs': [{'source': copy.deepcopy(area), 'output': copy.deepcopy(area)}]}


@pytest.mark.parametrize('root', [None, [], 42, 'invalid', {'version': 2, 'templates': []}])
def test_invalid_file_root_is_reported_without_overwriting_it(tmp_path, root):
    store = TemplateStore(tmp_path / 'templates.json')
    original = json.dumps(root)
    store.path.write_text(original, encoding='utf-8')
    with pytest.raises(ValueError):
        store.save(template())
    assert store.path.read_text(encoding='utf-8') == original


def test_editing_a_large_imported_catalog_does_not_discard_its_unrelated_layouts(tmp_path):
    store = TemplateStore(tmp_path / 'templates.json')
    names = [f'Layout {index}' for index in range(101)]
    store._write([dict(template(), name=name) for name in names])
    store.save(dict(template(), name=names[0], target_language='fr'))
    assert {v['name'] for v in store.load()} == set(names)
    with pytest.raises(ValueError):
        store.save(dict(template(), name='New layout'))
    store.delete(names[0])
    assert [v['name'] for v in store.load()] == names[1:]


def test_invalid_name_cannot_take_over_a_valid_layout_with_the_same_spelling(tmp_path):
    store = TemplateStore(tmp_path / 'templates.json')
    previous = store.save(dict(template(), name='None'))
    with pytest.raises(ValueError):
        store.save(dict(template(), name=None, target_language='fr'))
    assert store.load() == [previous]


@pytest.mark.parametrize('value', [None, [], 'bad', 1, True])
@pytest.mark.parametrize('level', ['pair', 'source', 'output'])
def test_invalid_region_types_are_validation_errors(value, level):
    data = template()
    if level == 'pair':
        data['pairs'][0] = value
    else:
        data['pairs'][0][level] = value
    with pytest.raises(ValueError):
        validate_template(data)


@pytest.mark.parametrize('number', [True, None, '0.2', -1, 2, float('nan'), float('inf'), 10 ** 400])
def test_invalid_coordinates_are_validation_errors(number):
    data = template()
    data['pairs'][0]['source']['rect'][0] = number
    with pytest.raises(ValueError):
        validate_template(data)


def test_seeded_monitor_changes_keep_regions_inside_the_available_screen():
    randomizer = random.Random(20260919)
    def screen(name, bounds):
        return SimpleNamespace(name=lambda: name, geometry=lambda: bounds)
    for _ in range(250):
        width, height = randomizer.randint(320, 7680), randomizer.randint(240, 4320)
        bounds = QtCore.QRect(randomizer.randint(-7680, 7680), randomizer.randint(-4320, 4320), width, height)
        x, y = randomizer.randrange(width - 60), randomizer.randrange(height - 24)
        region = QtCore.QRect(bounds.x()+x, bounds.y()+y, randomizer.randint(60, width-x), randomizer.randint(24, height-y))
        encoded = encode_rect(region, [screen('original', bounds)])
        assert decode_rect(encoded, [screen('original', bounds)]) == region
        changed = QtCore.QRect(-1920, -1080, randomizer.randint(60, 3840), randomizer.randint(24, 2160))
        with pytest.raises(ValueError, match='unavailable'):
            decode_rect(encoded, [screen('replacement', changed)])
        restored = decode_rect(encoded, [screen('original', changed)])
        assert changed.contains(restored)
        assert restored.width() >= 60 and restored.height() >= 24
