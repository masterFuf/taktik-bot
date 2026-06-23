"""Pure XML-dump parsers for the notifications surface.

IG renders some activity-feed rows with a BARE ``resource-id`` (e.g.
``activity_feed_newsfeed_story_row`` with no ``com.instagram.android:id/``
prefix) and others fully-qualified. Matching a resource-id by SUBSTRING of the
bare id is therefore the only robust strategy across both forms (and across IG
versions). These helpers take an lxml root (from ``dump_hierarchy``) and return
plain dicts, so they are unit-testable from a captured dump string.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .classifier import classify_row, clean_label, extract_time, row_has_action
from .classifier import _TRUNCATION_RE
from .row_layout import center, index_of_closest_row, parse_bounds, vertical_center


def _iter_rows(root, bare_id: str):
    """Yield nodes whose resource-id contains ``bare_id`` (bare or qualified)."""
    for node in root.iter("node"):
        if bare_id in (node.get("resource-id") or ""):
            yield node


def concat_text(node) -> str:
    """Join every descendant text / content-desc of ``node`` (order-preserving, deduped)."""
    parts: List[str] = []
    for descendant in node.iter():
        for attr in ("text", "content-desc"):
            val = descendant.get(attr)
            if val and val.strip():
                parts.append(val.strip())
    return " ".join(dict.fromkeys(parts)).strip()


def parse_feed_rows(root, row_bare_id: str, fragments: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    """Classify every activity-feed story row in the dump (top-to-bottom)."""
    rows: List[Dict[str, Any]] = []
    for node in _iter_rows(root, row_bare_id):
        full = concat_text(node)
        if not full:
            continue
        ntype, username = classify_row(full, fragments)
        rows.append({
            "type": ntype,
            "username": username,
            "time": extract_time(full),
            "text": full[:200],
            "label": clean_label(full),  # display label, trailing affordances/time/"…suite" stripped
            "has_action": row_has_action(full),
        })
    return rows


def node_text_deep(node) -> str:
    """Text of ``node`` or, if empty, of its first descendant that has text.

    A live (compressed) dump may put the text on a child TextView while the
    resource-id sits on the parent container, so reading only the parent's text
    misses it.
    """
    text = (node.get("text") or "").strip()
    if text:
        return text
    for descendant in node.iter():
        dt = (descendant.get("text") or "").strip()
        if dt:
            return dt
    return ""


def node_bounds_deep(node):
    """Bounds of ``node`` or its first descendant that has bounds."""
    box = parse_bounds(node.get("bounds", ""))
    if box:
        return box
    for descendant in node.iter():
        db = parse_bounds(descendant.get("bounds", ""))
        if db:
            return db
    return None


def _vcenter(node) -> Optional[float]:
    box = node_bounds_deep(node)
    return vertical_center(box) if box else None


def _collect_buttons(root, bare_id: str) -> List[Tuple[Tuple[int, int], float]]:
    """``[(center_xy, vertical_center)]`` for every node matching ``bare_id``."""
    out: List[Tuple[Tuple[int, int], float]] = []
    for node in root.iter("node"):
        if bare_id not in (node.get("resource-id") or ""):
            continue
        box = parse_bounds(node.get("bounds", ""))
        if box:
            out.append((center(box), vertical_center(box)))
    return out


def _find_row_control(
    root,
    row_bare_id: str,
    values: List[str],
    username: str,
    attrs: Tuple[str, ...],
) -> Optional[Tuple[int, int]]:
    """Tap center of a per-row control on the feed row for ``username``, or None.

    A control is any node whose ``attrs`` (e.g. ``content-desc`` and/or ``text``)
    matches one of ``values`` EXACTLY (case-insensitive). We pair it with the target
    row by **bounds containment**: the control's vertical center sits inside the
    matched row's vertical band. The activity feed rows are bare on resource-ids and
    the controls (Like / Reply) carry empty/foreign resource-ids, so bounds pairing
    — not DOM nesting — is the robust strategy. With an empty ``username`` the first
    row that owns a matching control is returned. Exact match avoids near-misses
    (e.g. "Unlike button" must NOT match "Like button").
    """
    wanted = {v.strip().lower() for v in values if v and v.strip()}
    if not wanted:
        return None
    controls: List[Tuple[Tuple[int, int], float]] = []
    for node in root.iter("node"):
        for attr in attrs:
            val = (node.get(attr) or "").strip().lower()
            if val and val in wanted:
                box = parse_bounds(node.get("bounds", ""))
                if box:
                    controls.append((center(box), vertical_center(box)))
                break
    if not controls:
        return None

    target = (username or "").strip().lower()
    for node in _iter_rows(root, row_bare_id):
        if target and target not in concat_text(node).lower():
            continue
        box = node_bounds_deep(node)
        if not box:
            continue
        top, bottom = box[1], box[3]
        for center_xy, vcenter in controls:
            if top <= vcenter <= bottom:
                return center_xy
    return None


# Estimated location of the inline "… more" / "… suite" expander WITHIN its text node.
# The expander is a ClickableSpan (no node of its own), appended just before the trailing
# time at the END of the (truncated, hence near-full) last line. We estimate it relative to
# the text node bounds so it scales across font sizes / devices: ~18% of the width in from
# the right edge, ~12% of the height up from the bottom (last line).
_MORE_FRAC_X = 0.18
_MORE_FRAC_Y = 0.12


def find_more_targets(root, row_bare_id: str) -> List[Dict[str, Any]]:
    """Estimated tap points for the inline "more"/"suite" expander on truncated rows.

    Returns ``[{key, point:(x,y)}]`` — ``key`` is the truncated text (used to detect
    expansion by growth / avoid re-tapping). Best-effort: the marker is a span with no
    bounds, so ``point`` is an estimate from the text node geometry (caller verifies the
    tap by re-reading, and recovers if it accidentally opened the post).
    """
    out: List[Dict[str, Any]] = []
    for row in _iter_rows(root, row_bare_id):
        text_node = None
        text_val = ""
        for descendant in row.iter():
            value = descendant.get("text") or ""
            if value and _TRUNCATION_RE.search(value):
                text_node, text_val = descendant, value
                break
        if text_node is None:
            continue
        box = parse_bounds(text_node.get("bounds", ""))
        if not box:
            continue
        x1, y1, x2, y2 = box
        point = (int(x2 - _MORE_FRAC_X * (x2 - x1)), int(y2 - _MORE_FRAC_Y * (y2 - y1)))
        out.append({"key": text_val, "point": point})
    return out


def parse_section_headers(root, header_bare_id: str) -> List[str]:
    """Visible time-section headers, top-to-bottom (deduped, order-preserving).

    Language-agnostic: matches the bare resource-id and returns whatever text the
    device shows ("Highlights" / "Today" / "Yesterday" / "Last 7 days" / "Aujourd'hui"
    …) so the narration speaks the user's own labels.
    """
    headers: List[str] = []
    for node in root.iter("node"):
        if header_bare_id in (node.get("resource-id") or ""):
            text = (node.get("text") or "").strip()
            if text and text not in headers:
                headers.append(text)
    return headers


def find_inline_like_target(
    root,
    row_bare_id: str,
    like_content_descs: List[str],
    username: str,
) -> Optional[Tuple[int, int]]:
    """Tap center of the inline "Like button" on the feed row for ``username``, or None.

    Comment and mention rows expose a CLICKABLE node whose ``content-desc`` is the
    localized "Like button" (empty resource-id, on the left of the row), so the
    comment can be liked directly from the notifications feed — no click-in. Matched
    by EXACT content-desc so the already-liked state ("Unlike button" / "Bouton Je
    n'aime plus") never matches and we never re-unlike.
    """
    return _find_row_control(root, row_bare_id, like_content_descs, username, ("content-desc",))


def find_row_reply_target(
    root,
    row_bare_id: str,
    reply_labels: List[str],
    username: str,
) -> Optional[Tuple[int, int]]:
    """Tap center of the inline "Reply" affordance on the feed row for ``username``.

    Comment / mention rows carry a "Reply" / "Répondre" Button (text node). Tapping it
    opens the standard comment thread focused on THAT comment, so the reply targets the
    right notification. Paired to the row by bounds containment (same strategy as the
    inline like). Matched on the ``text`` then ``content-desc`` attribute.
    """
    return _find_row_control(root, row_bare_id, reply_labels, username, ("text", "content-desc"))


def parse_request_rows(
    root,
    username_bare_id: str,
    accept_bare_id: str,
    ignore_bare_id: str,
) -> List[Dict[str, Any]]:
    """Pending follow-request rows: ``[{username, accept:(x,y)|None, ignore:(x,y)|None}]``.

    Container-INDEPENDENT: a compressed live ``dump_hierarchy`` collapses the
    layout containers (``follow_list_container``), but the username TextView and
    the Confirm/Delete buttons survive (text / clickable). So we collect every
    username node and every Confirm/Delete button across the tree and pair them by
    vertical-center proximity (each request row sits on its own horizontal band).
    ``follow_list_username`` is request-only (suggestions use a different id), so
    there is no cross-section contamination.
    """
    accepts = _collect_buttons(root, accept_bare_id)
    ignores = _collect_buttons(root, ignore_bare_id)
    accept_ys = [y for _, y in accepts]
    ignore_ys = [y for _, y in ignores]

    rows: List[Dict[str, Any]] = []
    for node in root.iter("node"):
        if username_bare_id not in (node.get("resource-id") or ""):
            continue
        username = node_text_deep(node)   # text may live on a child TextView
        y = _vcenter(node)
        if not username or y is None:
            continue
        ai = index_of_closest_row(y, accept_ys)
        ii = index_of_closest_row(y, ignore_ys)
        rows.append({
            "username": username,
            "accept": accepts[ai][0] if ai is not None else None,
            "ignore": ignores[ii][0] if ii is not None else None,
        })
    return rows


__all__ = [
    "concat_text", "parse_feed_rows", "parse_request_rows", "parse_section_headers",
    "find_inline_like_target", "find_row_reply_target", "find_more_targets",
]
