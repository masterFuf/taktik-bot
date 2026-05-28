"""Helpers for TikTok publish hashtag autocomplete."""

from __future__ import annotations

import time
from typing import Callable

from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.publish import (
    PUBLISH_SELECTORS,
    PublishSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import parse_bounds


LogFn = Callable[[str, str], None]


def tap_hashtag_suggestion_from_dump(
    device,
    expected_tag: str | None = None,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
    min_top: int = 480,
    settle_delay: float = 0.15,
    sleep: Callable[[float], None] = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Tap the best visible TikTok hashtag suggestion from the XML dump."""
    try:
        xml = device.dump_hierarchy(compressed=False)
        tree = etree.fromstring(xml.encode("utf-8"))
        expected = f"#{str(expected_tag or '').lstrip('#').strip()}".lower()
        candidates = []

        nodes = []
        for xpath in selectors.hashtag_suggestion_nodes:
            nodes.extend(tree.xpath(xpath))

        for node in nodes:
            text = node.attrib.get("text", "")
            bounds = node.attrib.get("bounds", "")
            parsed_bounds = parse_bounds(bounds)
            if parsed_bounds is None:
                continue

            left, top, right, bottom = parsed_bounds
            if top < min_top:
                continue

            exact = bool(expected and text.lower() == expected)
            candidates.append((not exact, top, left, text, right, bottom))

        if not candidates:
            return False

        candidates.sort()
        _, top, left, text, right, bottom = candidates[0]
        tap_x = (left + right) // 2
        tap_y = (top + bottom) // 2
        if log:
            log("debug", f"[hashtag] tapping suggestion {text!r} at ({tap_x}, {tap_y})")
        device.click(tap_x, tap_y)
        if settle_delay > 0:
            sleep(settle_delay)
        return True
    except Exception as exc:
        if log:
            log("debug", f"[hashtag] dump suggestion tap failed: {exc}")
        return False
