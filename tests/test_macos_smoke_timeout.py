import pytest

from tools.smoke_macos_bundle import smoke_timeout


def test_default_smoke_timeouts():
    assert smoke_timeout({}) == 120
    assert smoke_timeout({'CLICKNTRANSLATE_EXTENDED_SMOKE': '1'}) == 300


def test_ci_can_allow_slower_intel_rendering():
    assert smoke_timeout({'CLICKNTRANSLATE_SMOKE_TIMEOUT': '600'}) == 600


@pytest.mark.parametrize('value', ['0', '-1', 'invalid'])
def test_invalid_smoke_timeout_is_rejected(value):
    with pytest.raises(ValueError):
        smoke_timeout({'CLICKNTRANSLATE_SMOKE_TIMEOUT': value})
