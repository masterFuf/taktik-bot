"""Reusable TikTok publish progress detection."""

from __future__ import annotations

import re
from typing import Callable, Optional

from loguru import logger
from lxml import etree

from taktik.core.shared.device.ui_dump import dump_screen_size, parse_ui_dump
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import (
    PUBLISH_PROGRESS_SELECTORS,
    PublishProgressSelectors,
)
from taktik.core.social_media.tiktok.ui.xpath import parse_bounds


LogFn = Callable[[str, str], None]

PERCENT_TEXT_RE = re.compile(r"^\s*(\d{1,3})\s*%\s*$")

# Where TikTok draws its upload badge, as fractions of the screen the dump describes: a small
# label near the left edge, in the upper part of the screen. Measured on real captures of a
# 1080x2400 screen (left, top, width, height of the label, as fractions):
#   43.1.4 `x44`        [68,709][135,748]    0.063  0.295  0.062  0.016
#   46.6.3 `tvProgress` [56,344][127,383]    0.052  0.143  0.066  0.016
#   47.0.3 `tvProgress` [66,344][137,383]    0.061  0.143  0.066  0.016
# and refused: the "94%" of a profile right after a post, `qjj` [247,1388][342,1427],
# 0.229 0.578 0.088 0.016, which is no badge. The top bound sits between the lowest badge seen
# (0.295) and that profile label (0.578); the left and size bounds keep the margins the pixel
# bounds had on this screen (160 and 120 px of 1080, 80 px of 2400).
BADGE_MAX_LEFT = 0.15
BADGE_MAX_TOP = 0.40
BADGE_MAX_WIDTH = 0.11
BADGE_MAX_HEIGHT = 0.035


def _log_to_logger(level: str, message: str) -> None:
    getattr(logger, level, logger.debug)(message)


def extract_percent_value(value: str | None) -> Optional[int]:
    """Parse an `81%`-style progress label into an integer percentage."""
    if not value:
        return None

    match = PERCENT_TEXT_RE.match(value)
    if not match:
        return None

    percent = int(match.group(1))
    if 0 <= percent <= 100:
        return percent
    return None


def _percent_from_badge_ids(tree, selectors: PublishProgressSelectors, log: LogFn) -> Optional[int]:
    for xpath in selectors.publish_progress_indicator:
        try:
            nodes = tree.xpath(xpath)
        except etree.XPathError as exc:
            log("warning", f"[publishing] progress selector {xpath!r} is not a valid XPath: {exc}")
            continue
        for node in nodes:
            percent = extract_percent_value(node.attrib.get("text"))
            if percent is not None:
                return percent
    return None


def _is_where_the_badge_sits(bounds, screen_width: int, screen_height: int) -> bool:
    left, top, right, bottom = bounds
    return (
        left <= screen_width * BADGE_MAX_LEFT
        and top <= screen_height * BADGE_MAX_TOP
        and (right - left) <= screen_width * BADGE_MAX_WIDTH
        and (bottom - top) <= screen_height * BADGE_MAX_HEIGHT
    )


def _percent_from_badge_position(tree, selectors: PublishProgressSelectors, log: LogFn) -> Optional[int]:
    """A percent label where the badge sits, for a version whose badge id is not known yet."""
    screen = dump_screen_size(tree)
    if screen is None:
        log("warning", "[publishing] progress fallback skipped: the dump gives no screen size")
        return None
    screen_width, screen_height = screen

    for xpath in selectors.publish_progress_text_nodes:
        try:
            nodes = tree.xpath(xpath)
        except etree.XPathError as exc:
            log("warning", f"[publishing] progress selector {xpath!r} is not a valid XPath: {exc}")
            continue
        for node in nodes:
            percent = extract_percent_value(node.attrib.get("text"))
            if percent is None:
                continue
            bounds = parse_bounds(node.attrib.get("bounds", ""))
            if bounds is None:
                continue
            if _is_where_the_badge_sits(bounds, screen_width, screen_height):
                return percent
    return None


def get_publish_progress_percent(
    device,
    selectors: PublishProgressSelectors = PUBLISH_PROGRESS_SELECTORS,
    log: LogFn | None = None,
) -> Optional[int]:
    """Read TikTok's upload progress badge while publish is running.

    None when no badge is on screen, and also when the screen could not be read: that case is
    logged as a warning, so an unread screen never passes silently for a finished upload.
    """
    report = log or _log_to_logger
    try:
        xml = device.dump_hierarchy(compressed=False)
    except Exception as exc:
        report("warning", f"[publishing] progress unread: the screen could not be dumped: {exc}")
        return None

    tree = parse_ui_dump(xml)
    if tree is None:
        report("warning", "[publishing] progress unread: the dump is empty or does not parse")
        return None

    percent = _percent_from_badge_ids(tree, selectors, report)
    if percent is not None:
        return percent
    return _percent_from_badge_position(tree, selectors, report)
