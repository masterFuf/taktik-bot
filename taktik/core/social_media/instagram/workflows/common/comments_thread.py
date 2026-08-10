"""Reading the comments thread of a post from a UI dump.

The counterpart of `notifications/dump_parsing.py`, for the comments surface. Pure functions
over an ElementTree root: no device, no side effect, so the pairing rules below are testable
against captured dumps.

A comment row has no resource-id of its own, so rows are identified by GEOMETRY, exactly like
the notifications feed pairs a control to its row: a control belongs to the comment whose
username sits inside the control's vertical span. Observed on a real dump (2026-02-08):

    ViewGroup                                                    [0,185][576,302]   <- the row
      ImageView  desc="Go to commenter42's profile"                [24,203][78,257]
      ViewGroup                                                  [84,185][492,302]
        ViewGroup desc='commenter42 '                              [84,197][492,255]
          Button  desc=''      text='commenter42'                  [98,197][189,222]  <- username
        Button    desc='Reply' text='Reply'                      [98,255][170,302]
        Button    desc='See translation'                         [170,255][325,302]
      Button      desc='1 likes. Double tap to like comment...'  [492,185][576,275] <- like
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Bounds geometry belongs to the shared owner; re-exported here so the existing
# callers of this module keep working.
from taktik.core.shared.device.ui_dump import center, parse_bounds  # noqa: F401


def _matches_any(value: str, tokens: List[str]) -> bool:
    low = (value or "").lower()
    return any(token.lower() in low for token in tokens if token)


def _username_center_y(root, target: str) -> Optional[int]:
    """Vertical centre of `target`'s username button — the anchor every row control pairs to."""
    for node in root.iter("node"):
        if (node.get("content-desc") or "") != "":
            continue
        if (node.get("text") or "").strip().lstrip("@").lower() != target:
            continue
        box = parse_bounds(node.get("bounds", ""))
        if box:
            return (box[1] + box[3]) // 2
    return None


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

    username_center_y = _username_center_y(root, target)
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


def find_comment_reply_target(
    root,
    username: str,
    reply_labels: List[str],
) -> Optional[Tuple[int, int, int, int]]:
    """The bounds of the Reply affordance on `username`'s comment row, or None.

    Paired by READING ORDER, not by containment like the heart: the heart spans the whole
    row so the username falls inside it, but Reply sits BELOW the username, in the text
    column. So the right button is the first reply-labelled node between our author and the
    NEXT author on screen — a few dozen pixels separate it from the following row's own
    Reply, and answering under the wrong comment is not recoverable.

    Matched on the button's text OR its content-desc, since Instagram fills both.
    """
    target = (username or "").strip().lstrip("@").lower()
    if not target:
        return None

    wanted = {label.strip().lower() for label in reply_labels if label and label.strip()}
    if not wanted:
        return None

    anchors = _username_anchors(root)
    own_center = next((c for handle, c, _ in anchors if handle == target), None)
    if own_center is None:
        return None
    # Everything below the next author belongs to the next comment.
    next_top = next((top for _, c, top in anchors if c > own_center), None)

    best: Optional[Tuple[int, Tuple[int, int, int, int]]] = None
    for node in root.iter("node"):
        label = (node.get("text") or "").strip().lower() or (node.get("content-desc") or "").strip().lower()
        if label not in wanted:
            continue
        box = parse_bounds(node.get("bounds", ""))
        if not box:
            continue
        node_center = (box[1] + box[3]) // 2
        if node_center <= own_center:
            continue
        if next_top is not None and node_center >= next_top:
            continue
        if best is None or node_center < best[0]:
            best = (node_center, box)
    return best[1] if best else None


def _username_anchors(root) -> List[Tuple[str, int, int]]:
    """Every username button on screen as ``(handle, vertical_centre, top)``, top to bottom."""
    anchors: List[Tuple[str, int, int]] = []
    for node in root.iter("node"):
        if (node.get("content-desc") or "") != "":
            continue
        handle = (node.get("text") or "").strip().lstrip("@").lower()
        if not handle:
            continue
        box = parse_bounds(node.get("bounds", ""))
        if box:
            anchors.append((handle, (box[1] + box[3]) // 2, box[1]))
    anchors.sort(key=lambda item: item[1])
    return anchors


__all__ = [
    "parse_bounds",
    "center",
    "find_comment_like_target",
    "find_comment_reply_target",
]
