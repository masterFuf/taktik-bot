"""Shared primitives for reading an Android hierarchy dump.

Canonical owner of the bounds geometry of a dump node: the string rendered by the
automation layer in the bounds attribute. These functions are PURE, with no device,
so they are testable from a captured dump.

The same parser had been copied into several surfaces. New code must import this
owner; the remaining copies are debt to pay down.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

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


__all__ = ["parse_bounds", "vertical_center", "center", "index_of_closest_row"]
