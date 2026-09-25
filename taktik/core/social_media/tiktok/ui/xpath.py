"""Small XPath helpers shared by TikTok workflows and UI detectors."""

from __future__ import annotations

from typing import Iterable
# Bounds geometry belongs to the shared owner. The local copy read the numbers with a
# digits-only pattern, which silently dropped the minus sign of an off-screen
# coordinate; the owner keeps it.
from taktik.core.shared.device.ui_dump import parse_bounds  # noqa: F401


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


