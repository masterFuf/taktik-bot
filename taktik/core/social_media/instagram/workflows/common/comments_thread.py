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


def _normalise(value: Optional[str]) -> str:
    """A label reduced to comparable form.

    Compose pads its labels with no-break spaces (U+00A0, sometimes U+202F), which look
    like ordinary spaces in a dump and in an editor while comparing unequal. Collapsing on
    the Unicode whitespace class handles every one of them without putting an invisible
    character in this file.
    """
    return re.sub(r"\s+", " ", value or "").strip().lstrip("@").lower()


# An Instagram handle: letters, digits, dots, underscores, at most 30 of them. This is what
# tells a username label apart from everything else in a comment row that carries text.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")


def _handle_shape(node) -> Optional[str]:
    """The handle a node's text spells, or None when the text is not a handle at all.

    Excludes a purely numeric label: a like counter is indistinguishable from a username by
    attributes alone, and on this surface it is never one.
    """
    text = (node.get("text") or "").strip().lstrip("@")
    if not text or text.isdigit() or not _HANDLE_RE.match(text):
        return None
    return text.lower()


def _username_nodes(root) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """Every username label on screen as ``(handle, bounds)``, document order.

    Two shapes exist, both real, and they must NOT be mixed in one pass:

    - IG 442 (Compose): the username TextView repeats its text in content-desc (with a
      trailing no-break space). This is the shape that broke everything -- the first version
      required an EMPTY content-desc, so on 442 no anchor was ever found and comment liking
      and replying both silently stopped working.
    - pre-442: the username Button carries text and an EMPTY content-desc.

    The Compose rule additionally requires a TextView, and that is not decoration. On 442 the
    row's OTHER labels repeat themselves in content-desc too -- "Reply", "See translation",
    the timestamp, "Author" -- so desc == text alone would collect them and, worse, would
    collect "Reply" on the LEGACY layout as well, wiping out every real anchor there. Measured
    on a real 442 thread, TextView + desc == text + handle shape yields exactly the usernames:
    "Reply" is a View, a @mention inside a body is a Button with an empty content-desc, and the
    feed showing THROUGH the sheet contributes a Button too.

    Preferring the Compose shape when it is present is what keeps that @mention from being read
    as that person's own comment row -- it only qualifies under the legacy rule, which 442 never
    reaches. The body itself is excluded by shape alone: it reads "<user> said <text>", which has
    spaces and is therefore not a handle.
    """
    compose: List[Tuple[str, Tuple[int, int, int, int]]] = []
    legacy: List[Tuple[str, Tuple[int, int, int, int]]] = []
    for node in root.iter("node"):
        handle = _handle_shape(node)
        if not handle:
            continue
        box = parse_bounds(node.get("bounds", ""))
        if not box:
            continue
        desc = _normalise(node.get("content-desc"))
        if not desc:
            legacy.append((handle, box))
        elif desc == handle and (node.get("class") or "").endswith("TextView"):
            compose.append((handle, box))
    return compose or legacy


def _username_center_y(root, target: str) -> Optional[int]:
    """Vertical centre of `target`'s username label — the anchor every row control pairs to."""
    for handle, box in _username_nodes(root):
        if handle == target:
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


def read_comment_texts(root, connectors: Optional[List[str]] = None) -> List[Tuple[str, str]]:
    """Every comment visible on screen as ``(author, text)``, top to bottom.

    IG 442 stopped giving the comment body a resource-id, so the id-based selector returns
    nothing and the persona reader came back empty on every post. The body is still there: it
    is the node of the row that spells "<author> <connector> <text>" in BOTH text and
    content-desc -- exactly the same string, which is how it is told apart from the timestamp
    and the "Reply" / "See translation" labels that also repeat themselves.

    Pairing is by the row band: a body belongs to the author whose label sits above it and
    before the next author's. ``connectors`` are the localized "said" fragments; when none
    matches, only the handle is stripped, so an unknown language degrades to a slightly noisy
    line rather than to nothing.
    """
    anchors = _username_anchors(root)
    if not anchors:
        return []

    bands = []
    for index, (handle, center, _top) in enumerate(anchors):
        next_center = anchors[index + 1][1] if index + 1 < len(anchors) else None
        bands.append((handle, center, next_center))

    stems = [c.strip().lower() for c in (connectors or []) if c and c.strip()]
    out: List[Tuple[str, str]] = []
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        if not text or " " not in text:
            continue
        if _normalise(node.get("content-desc")) != _normalise(text):
            continue
        box = parse_bounds(node.get("bounds", ""))
        if not box:
            continue
        center = (box[1] + box[3]) // 2
        for handle, anchor_center, next_center in bands:
            if center < anchor_center:
                continue
            if next_center is not None and center >= next_center:
                continue
            lowered = text.lower()
            if not lowered.startswith(handle):
                break  # a label of that row, not its body
            body = text[len(handle):].strip()
            for stem in stems:
                if body.lower().startswith(stem):
                    body = body[len(stem):].strip()
                    break
            if body:
                out.append((handle, body))
            break
    return out


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
    """Every username label on screen as ``(handle, vertical_centre, top)``, top to bottom."""
    anchors = [
        (handle, (box[1] + box[3]) // 2, box[1])
        for handle, box in _username_nodes(root)
    ]
    anchors.sort(key=lambda item: item[1])
    return anchors


__all__ = [
    "parse_bounds",
    "center",
    "find_comment_like_target",
    "find_comment_reply_target",
    "read_comment_texts",
]
