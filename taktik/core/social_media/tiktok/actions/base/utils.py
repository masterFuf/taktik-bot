"""
TikTok Action Utilities

Re-exports shared ActionUtils/parse_count and adds TikTok-specific overrides.
TikTok usernames: 2-24 characters.
"""

import re as _re
from typing import List as _List

from taktik.core.shared.actions.utils import ActionUtils as _SharedActionUtils, parse_count


def extract_resource_id(selectors: _List[str]) -> str:
    """Extract resource-id value from the first xpath selector containing one.

    e.g. '//*[@resource-id="com.zhiliaoapp.musically:id/z05"]' → 'com.zhiliaoapp.musically:id/z05'

    LIMITED ON PURPOSE, and do not extend it. It matches `@resource-id="…"` and nothing else, so
    it returns '' for the `contains(@resource-id, …)` form the profile catalogue uses — which is
    how the whole profile read died silently for months, every caller taking an `if rid:` false
    branch and returning defaults.

    Teaching this to parse `contains()` would repair the symptom and keep the disease: a second
    way to address a node, in a codebase where the first one is `device.xpath(selector)`. Read a
    selector list with `first_matching` / `first_text` below instead.
    """
    for sel in selectors:
        m = _re.search(r'@resource-id="([^"]+)"', sel)
        if m:
            return m.group(1)
    return ''


def first_matching(device, selectors: _List[str]) -> list:
    """Elements of the first selector in the list that matches anything, or [].

    The loop this replaces was written out five times (`profile_actions`, `followers/interaction`
    ×2, `followers/profile_data`, and the profile extractor that had it WRONG). A selector list
    is an ordered set of alternatives — the package differs between the musically and trill
    builds — so "first that finds something wins" is the contract, not "the first one".
    """
    for sel in selectors or ():
        try:
            found = device.xpath(sel).all()
        except Exception:
            continue
        if found:
            return found
    return []


def first_text(device, selectors: _List[str], default: str = '') -> str:
    """Text of the first element the selector list finds, stripped.

    `.text`, not `.get_text()`: an xpath match is an `XMLElement`, and calling the selector API on
    it raises. That difference is exactly what separated the working reader from the broken one.
    """
    for element in first_matching(device, selectors):
        try:
            text = element.text
        except Exception:
            continue
        if text and text.strip():
            return text.strip()
    return default


class ActionUtils(_SharedActionUtils):
    """TikTok-specific ActionUtils.
    
    Inherits all shared utilities. Overrides:
    - is_valid_username: uses TikTok limits (2-24 chars)
    """
    
    @staticmethod
    def is_valid_username(username: str, min_length: int = 2, max_length: int = 24) -> bool:
        """Validate TikTok username format (2-24 characters)."""
        return _SharedActionUtils.is_valid_username(username, min_length=2, max_length=24)
