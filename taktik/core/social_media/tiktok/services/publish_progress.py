"""Reusable TikTok publish progress detection."""

from __future__ import annotations

import re
from typing import Callable, Optional

from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.publish import (
    PUBLISH_SELECTORS,
    PublishSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import parse_bounds, to_lxml


LogFn = Callable[[str, str], None]

PERCENT_TEXT_RE = re.compile(r"^\s*(\d{1,3})\s*%\s*$")


def extract_percent_value(value: str | None) -> Optional[int]:
    """Parse an `81%`-style progress label into an integer percentage."""
    if not value:
        return None

    match = PERCENT_TEXT_RE.match(value)
    if not match:
        return None

    try:
        percent = int(match.group(1))
    except Exception:
        return None

    if 0 <= percent <= 100:
        return percent
    return None


def get_publish_progress_percent(
    device,
    selectors: PublishSelectors = PUBLISH_SELECTORS,
    log: LogFn | None = None,
) -> Optional[int]:
    """Read TikTok's top-left upload progress badge while publish is running."""
    try:
        xml = device.dump_hierarchy(compressed=False)
        tree = etree.fromstring(xml.encode("utf-8"))

        for xpath in selectors.publish_progress_indicator:
            try:
                nodes = tree.xpath(to_lxml(xpath))
            except Exception:
                continue
            for node in nodes:
                percent = extract_percent_value(node.attrib.get("text"))
                if percent is not None:
                    return percent

        for xpath in selectors.publish_progress_text_nodes:
            for node in tree.xpath(xpath):
                percent = extract_percent_value(node.attrib.get("text"))
                if percent is None:
                    continue
                bounds = parse_bounds(node.attrib.get("bounds", ""))
                if bounds is None:
                    continue
                left, top, right, bottom = bounds
                if left > 160 or top > 320:
                    continue
                if (right - left) > 120 or (bottom - top) > 80:
                    continue
                return percent
    except Exception as exc:
        if log:
            log("debug", f"[publishing] progress parse failed: {exc}")
    return None
