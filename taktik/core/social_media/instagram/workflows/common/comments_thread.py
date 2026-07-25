"""Reading the comments thread of a post from a UI dump.

The counterpart of `notifications/dump_parsing.py`, for the comments surface. Pure functions
over an ElementTree root: no device, no side effect, so the pairing rules below are testable
against captured dumps.

A comment row has no resource-id of its own, so rows are identified by GEOMETRY, exactly like
the notifications feed pairs a control to its row: a control belongs to the comment whose
username sits inside the control's vertical span. Observed on a real dump (2026-02-08):

    ViewGroup                                                    [0,185][576,302]   <- the row
      ImageView  desc="Go to dianeou38's profile"                [24,203][78,257]
      ViewGroup                                                  [84,185][492,302]
        ViewGroup desc='dianeou38 '                              [84,197][492,255]
          Button  desc=''      text='dianeou38'                  [98,197][189,222]  <- username
        Button    desc='Reply' text='Reply'                      [98,255][170,302]
        Button    desc='See translation'                         [170,255][325,302]
      Button      desc='1 likes. Double tap to like comment...'  [492,185][576,275] <- like
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def parse_bounds(raw: str) -> Optional[Tuple[int, int, int, int]]:
    """`"[l,t][r,b]"` -> `(left, top, right, bottom)`, or None when unparseable."""
    match = _BOUNDS_RE.match((raw or "").strip())
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def center(box: Tuple[int, int, int, int]) -> Tuple[int, int]:
    left, top, right, bottom = box
    return (left + right) // 2, (top + bottom) // 2


def _matches_any(value: str, tokens: List[str]) -> bool:
    low = (value or "").lower()
    return any(token.lower() in low for token in tokens if token)


def find_comment_like_target(
    root,
    username: str,
    like_tokens: List[str],
    unlike_tokens: List[str],
) -> Optional[Dict[str, Any]]:
    """Where to tap to like `username`'s comment, and whether it is already liked.

    Returns ``{'bounds': (left, top, right, bottom), 'already_liked': bool}``, or None when
    the row or its like control cannot be found. The full box is returned rather than a
    point so the caller can hand it to `human_tap`, which samples a varied spot inside the
    real control instead of hitting the same pixel every time.

    The already-liked test runs FIRST and wins. That order is not cosmetic: in French the
    liked state reads "ne plus aimer le commentaire", which CONTAINS the not-liked token
    "aimer le commentaire", so checking the positive token first would tap a liked comment
    and silently UNLIKE it while reporting a like. A control that matches neither token is
    reported as unknown state (`already_liked=True`) so the caller does nothing — a missed
    like costs nothing, an accidental unlike corrupts both the target's post and our count.
    """
    target = (username or "").strip().lstrip("@").lower()
    if not target:
        return None

    username_center_y: Optional[int] = None
    for node in root.iter("node"):
        if (node.get("content-desc") or "") != "":
            continue
        if (node.get("text") or "").strip().lower().lstrip("@") != target:
            continue
        box = parse_bounds(node.get("bounds", ""))
        if box:
            username_center_y = (box[1] + box[3]) // 2
            break
    if username_center_y is None:
        return None

    for node in root.iter("node"):
        desc = node.get("content-desc") or ""
        if not desc:
            continue
        liked = _matches_any(desc, unlike_tokens)
        if not liked and not _matches_any(desc, like_tokens):
            continue
        box = parse_bounds(node.get("bounds", ""))
        if not box or not (box[1] <= username_center_y <= box[3]):
            continue
        return {"bounds": box, "already_liked": liked}

    return None


__all__ = [
    "parse_bounds",
    "center",
    "find_comment_like_target",
]
