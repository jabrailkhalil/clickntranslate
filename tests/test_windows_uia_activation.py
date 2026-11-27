"""A generated UIA coclass must not depend on a registered textual ProgID."""
from unittest.mock import Mock

import pytest

import selection_platform
from test_windows_uia_contract import CUIAutomation, IUIAutomation, IUIAutomationTextPattern, scenario


@pytest.mark.parametrize('allow_copy_fallback', [False, True])
def test_generated_coclass_reads_selection_without_a_registered_progid(scenario, monkeypatch, allow_copy_fallback):
    scenario.seed('mta')
    attempts = []

    def create(target, **kwargs):
        attempts.append((target, kwargs))
        if target is not CUIAutomation:
            raise OSError(-2147221005, 'synthetic unregistered textual ProgID')
        return scenario.create(target, **kwargs)

    monkeypatch.setattr(scenario.client, 'CreateObject', create)
    fallback = Mock(return_value='Copied fallback')
    monkeypatch.setattr(selection_platform, '_read_selection_via_copy', fallback)

    assert selection_platform.read_selected_text(allow_copy_fallback=allow_copy_fallback) == 'Native selection'
    assert attempts == [(CUIAutomation, {'interface': IUIAutomation})]
    assert scenario.queries == [IUIAutomationTextPattern]
    assert scenario.interfaces == [IUIAutomation]
    assert scenario.modules == ['UIAutomationCore.dll']
    assert scenario.local.refs == 1
    assert scenario.events[-1][0] == 'uninit' and scenario.events[-1][2] == 0
    fallback.assert_not_called()
