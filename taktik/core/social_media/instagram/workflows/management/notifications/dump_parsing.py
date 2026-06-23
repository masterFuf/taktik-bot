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
from .row_layout import center, parse_bounds


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


def _center_of(node, bare_id: str) -> Optional[Tuple[int, int]]:
    for descendant in node.iter():
        if bare_id in (descendant.get("resource-id") or ""):
            box = parse_bounds(descendant.get("bounds", ""))
            if box:
                return center(box)
    return None


def _text_of(node, bare_id: str) -> str:
    for descendant in node.iter():
        if bare_id in (descendant.get("resource-id") or ""):
            return (descendant.get("text") or "").strip()
    return ""


def parse_request_rows(
    root,
    container_bare_id: str,
    username_bare_id: str,
    accept_bare_id: str,
    ignore_bare_id: str,
) -> List[Dict[str, Any]]:
    """Pending follow-request rows: ``[{username, accept:(x,y)|None, ignore:(x,y)|None}]``.

    Username + Confirm/Delete tap points are resolved WITHIN each request
    container, so a tap always targets the right row (no cross-row mismatch).
    """
    rows: List[Dict[str, Any]] = []
    for container in _iter_rows(root, container_bare_id):
        username = _text_of(container, username_bare_id)
        if not username:
            continue
        rows.append({
            "username": username,
            "accept": _center_of(container, accept_bare_id),
            "ignore": _center_of(container, ignore_bare_id),
        })
    return rows


__all__ = ["concat_text", "parse_feed_rows", "parse_request_rows"]
