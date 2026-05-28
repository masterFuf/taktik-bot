"""Helpers for TikTok publish gallery/upload UI."""

from __future__ import annotations

from typing import Callable

from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.publish import (
    PUBLISH_SELECTORS,
    PublishSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import parse_bounds


LogFn = Callable[[str, str], None]


def tap_upload_button_from_dump(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
    log: LogFn | None = None,
) -> bool:
    """Tap the visible TikTok gallery button by reading XML bounds."""
    try:
        xml = device.dump_hierarchy(compressed=False)
        tree = etree.fromstring(xml.encode("utf-8"))
        candidates = []

        for rid, xpath in selectors.upload_dump_selectors:
            for node in tree.xpath(xpath):
                bounds = node.attrib.get("bounds", "")
                parsed_bounds = parse_bounds(bounds)
                if parsed_bounds is None:
                    continue

                left, top, right, bottom = parsed_bounds
                width = right - left
                height = bottom - top
                if width <= 12 or height <= 12:
                    continue
                if node.attrib.get("visible-to-user") == "false" or node.attrib.get("enabled") == "false":
                    continue

                clickable = node.attrib.get("clickable") == "true"
                candidates.append((not clickable, rid, left, top, right, bottom))

        if not candidates:
            return False

        candidates.sort()
        _, rid, left, top, right, bottom = candidates[0]
        tap_x = (left + right) // 2
        tap_y = (top + bottom) // 2
        if log:
            log("debug", f"[upload] dump bounds tap {rid}: ({tap_x}, {tap_y})")
        device.click(tap_x, tap_y)
        return True
    except Exception as exc:
        if log:
            log("debug", f"[upload] dump bounds tap failed: {exc}")
        return False
