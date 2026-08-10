"""Small XPath helpers shared by TikTok workflows and UI detectors."""

from __future__ import annotations

import re
from typing import Iterable
# Bounds geometry belongs to the shared owner. The local copy read the numbers with a
# digits-only pattern, which silently dropped the minus sign of an off-screen
# coordinate; the owner keeps it.
from taktik.core.shared.device.ui_dump import parse_bounds  # noqa: F401


CLASS_STEP_RE = re.compile(
    r'(/{1,2})([a-zA-Z][a-zA-Z0-9]*(?:\.[a-zA-Z][a-zA-Z0-9]*)+)'
)


def to_lxml(xpath: str) -> str:
    """Translate uiautomator-ish class steps into lxml-compatible node filters."""
    return CLASS_STEP_RE.sub(r'\1node[@class="\2"]', xpath)


def find_element(device, selectors: Iterable[str], timeout: float = 2.0):
    for xpath in selectors:
        try:
            element = device.xpath(xpath)
            if element.wait(timeout=timeout):
                return element
        except Exception:
            continue
    return None


def tap_element(device, selectors: Iterable[str], timeout: float = 2.0) -> bool:
    element = find_element(device, selectors, timeout)
    if not element:
        return False

    try:
        element.click()
        return True
    except Exception:
        return False


