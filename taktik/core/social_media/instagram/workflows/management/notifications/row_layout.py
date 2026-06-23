"""Pure geometry helpers for pairing per-row controls on the activity surface.

On the follow-requests sub-screen each request row shows a username on the left
and Confirm/Delete buttons on the right, all on the same horizontal band. To act
on a specific username we pair its label box with the action button on the same
row by vertical-center proximity. Pure functions (no device) so they are
unit-testable; the workflow feeds them real element bounds.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Tuple

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def parse_bounds(value: str) -> Optional[Tuple[int, int, int, int]]:
    """Parse an Android bounds string ``"[x1,y1][x2,y2]"`` into a 4-tuple."""
    if not value:
        return None
    match = _BOUNDS_RE.search(value)
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def vertical_center(bounds: Sequence[int]) -> float:
    """Vertical center (y) of a bounds 4-tuple ``(x1, y1, x2, y2)``."""
    return (bounds[1] + bounds[3]) / 2.0


def center(bounds: Sequence[int]) -> Tuple[int, int]:
    """Center point ``(x, y)`` of a bounds 4-tuple."""
    return ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)


def index_of_closest_row(target_y: float, candidate_ys: List[float]) -> Optional[int]:
    """Index of the candidate whose vertical center is closest to ``target_y``.

    Returns ``None`` when there are no candidates. Used to map a username row to
    its Confirm/Delete button (and vice-versa) without relying on DOM nesting.
    """
    if not candidate_ys:
        return None
    return min(range(len(candidate_ys)), key=lambda i: abs(candidate_ys[i] - target_y))


__all__ = ["parse_bounds", "vertical_center", "center", "index_of_closest_row"]
