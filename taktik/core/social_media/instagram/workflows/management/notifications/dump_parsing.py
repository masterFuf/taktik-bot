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

from .classifier import classify_row, extract_time, row_has_action
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


__all__ = ["concat_text", "parse_feed_rows", "parse_request_rows"]
