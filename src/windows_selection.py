"""Read selected text from the foreground Windows control via UI Automation."""

from __future__ import annotations

import logging

logger = logging.getLogger("clickntranslate.selection")


def read_windows_selected_text():
    try:
        return _read_via_comtypes()
    except ImportError:
        logger.debug("UI Automation unavailable (comtypes not installed)")
    except Exception:
        logger.debug("UI Automation selection read failed", exc_info=True)
    return ""


def _read_via_comtypes():
    import comtypes.client

    automation = comtypes.client.CreateObject("UIAutomationClient.CUIAutomation")
    element = automation.GetFocusedElement()
    if element is None:
        return ""
    try:
        text_pattern = element.GetCurrentPattern(10014)  # UIA_TextPatternId
        if text_pattern is not None:
            ranges = text_pattern.GetSelection()
            if ranges is not None and int(getattr(ranges, "Length", 0) or 0) > 0:
                parts = []
                for index in range(int(ranges.Length)):
                    parts.append(str(ranges.GetElement(index).GetText(-1) or ""))
                text = "".join(parts).strip()
                if text:
                    return text
    except Exception:
        logger.debug("TextPattern selection read failed", exc_info=True)
    return ""
