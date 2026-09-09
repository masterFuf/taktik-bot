"""Shared primitives for reading an Android hierarchy dump.

Canonical owner of two things a dump reader needs, both PURE and testable from a captured file:

1. THE BOUNDS GEOMETRY of a dump node — the string the automation layer renders in the bounds
   attribute. The same parser had been copied into several surfaces. New code must import this
   owner; the remaining copies are debt to pay down.

2. THE TREE ITSELF, normalised the way `d.xpath()` sees it — see `parse_ui_dump`.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

from lxml import etree

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(value: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse an Android ``bounds`` string into a 4-tuple, or None."""
    if not value:
        return None
    match = _BOUNDS_RE.search(value)
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def vertical_center(bounds: Sequence[int]) -> float:
    """Vertical centre of a ``(x1, y1, x2, y2)`` tuple."""
    return (bounds[1] + bounds[3]) / 2.0


def center(bounds: Sequence[int]) -> Tuple[int, int]:
    """Centre of a ``(x1, y1, x2, y2)`` tuple."""
    return ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)


def index_of_closest_row(target_y: float, candidate_ys: List[float]) -> Optional[int]:
    """Index of the candidate whose vertical centre is closest to ``target_y``.

    Returns None with no candidate. Used to pair a label with its action button on the
    same horizontal band, when the DOM nesting does not relate them.
    """
    if not candidate_ys:
        return None
    return min(range(len(candidate_ys)), key=lambda i: abs(candidate_ys[i] - target_y))


# Same normalisation uiautomator2 applies to a tag name: anything that cannot appear in an XML
# name becomes an underscore, so `com.facebook.compose.view.MetaComposeView` survives and a class
# carrying a `$` (inner classes do) does not produce an unparsable tree.
_INVALID_TAG_CHARS = re.compile(r"[$@#\s]")


def _safe_tag(value: str) -> str:
    return _INVALID_TAG_CHARS.sub("_", value)


def parse_ui_dump(xml_content: Optional[str]):
    """The dump as a tree whose TAGS are widget classes — None when there is nothing to parse.

    THE BUG THIS REMOVES. The device returns AOSP XML, where every element is `<node>` and the
    widget type is an ATTRIBUTE:

        <node class="android.widget.TextView" text="the bio" .../>

    `uiautomator2` never shows that tree to a selector. Its `PageSource.root` rewrites it first —
    the tag becomes the class, and `class` is POPPED — so inside `d.xpath(...)` the element really
    is `<android.widget.TextView>` and `@class` no longer exists. Every one of our ~1 000
    class-based selectors is written in that idiom, and rightly so.

    Code parsing `get_xml_dump()` with plain lxml saw the OTHER tree. There
    `//android.widget.TextView` matches nothing, silently. Measured on a real 2026-09-09 dump:
    0 matches for the selector production used, 1 for `//node[@class="android.widget.TextView"]`,
    and that 1 was the profile bio. It is how the Instagram bio stopped being read on 2026-08-26 —
    the day the IG 442 catalogue began applying — while the name and the counters, matched by
    resource-id and therefore untouched by tag names, kept working and hid the loss for two weeks.

    The fix is not a second idiom for the selectors; two idioms is how they drift apart. It is to
    hand the lxml readers the SAME tree the selectors were written against. `class` is dropped
    rather than kept, deliberately: leaving it would make `@class` work here and fail under
    `d.xpath()`, which is exactly the asymmetry being removed.
    """
    if not xml_content:
        return None
    try:
        root = etree.fromstring(xml_content.encode("utf-8"))
    except Exception:
        return None
    for node in root.xpath("//node"):
        node.tag = _safe_tag(node.attrib.pop("class", "")) or "node"
    return root


__all__ = ["parse_bounds", "vertical_center", "center", "index_of_closest_row", "parse_ui_dump"]
