"""Pure parser for the "Suggestions" zone at the bottom of the notifications screen.

This is NOT the "Discover people" surface. The structure it parses:

    'Suggestions'            <- section header, activity_feed_header_row
    [igds_people_cell]       <- the row, clickable
        '<display name>'     <- bare TextView
        '<social context>'   <- bare TextView
        [igds_button]        <- the button, clickable
            '<state label>'  <- bare TextView
        [close]              <- clickable ImageView

The FIELDS carry no resource-id, but the row and the button do. A geometry-only
fallback is kept for layouts that do not render the cell, since the same APK is
served with different layouts.

The anchor is the BUTTON, not the name: it carries the relationship state, and its
label goes through ``classify_follow_state`` — the same function as the profile
header, hence the same language coverage.

The tap targets the label bounds although the label is not clickable: the clickable
ancestor receives the event.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from taktik.core.shared.device.ui_dump import center, parse_bounds, vertical_center

# Vertical step between two rows, as a FRACTION of the screen height (never pixels:
# another device does not have the same step). A row's band is half of it; beyond
# that, the neighbouring row starts.
_ROW_PITCH_RATIO = 198 / 2400


def iter_text_nodes(root):
    """Nodes carrying visible text, with their parsed bounds."""
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        if not text:
            continue
        bounds = parse_bounds(node.get("bounds") or "")
        if bounds:
            yield node, text, bounds


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _has_id(node, resource_id: Optional[str]) -> bool:
    return bool(resource_id) and resource_id in (node.get("resource-id") or "")


def find_suggestions_header_y(root, header_texts: Sequence[str],
                              header_resource_id: Optional[str] = None) -> Optional[int]:
    """Top ordinate of the "Suggestions" header, or None when it is off screen.

    The header is TEXT, so it is the one language-dependent part of this module and
    the only reason the parser needs a localized catalog.

    The label is required to match EXACTLY, and to sit on a section-header node when
    the caller provides its resource-id. A "contains" match on any TextView also hit
    the "Suggested for you: A, B and 3 others" notification, placing the anchor far
    too high and reading every notification below it — each with its own follow
    button — as a suggestion.
    """
    if root is None:
        return None
    wanted = {_normalize(h) for h in (header_texts or []) if h and h.strip()}
    if not wanted:
        return None
    for node, text, bounds in iter_text_nodes(root):
        if header_resource_id and not _has_id(node, header_resource_id):
            continue
        if _normalize(text) in wanted:
            return bounds[1]
    return None


def _row_from_cell(cell, profile_selectors, classify_state,
                   button_resource_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """A row read as a SUBTREE, when the surface exposes its cell.

    The state label is looked up in the button's subtree, or failing that among the
    cell texts that classify. A row whose button does not classify is still returned,
    with ``state`` set to None: that is a locale gap, and the caller must be able to
    report it rather than watch the row vanish.
    """
    texts = [(text, bounds) for _node, text, bounds in iter_text_nodes(cell)]
    if not texts:
        return None

    button_nodes = [n for n in cell.iter("node") if _has_id(n, button_resource_id)]
    button_texts = [(text, bounds)
                    for node in button_nodes
                    for _n, text, bounds in iter_text_nodes(node)]

    state_label, button_bounds, state = "", None, None
    for text, bounds in (button_texts or texts):
        resolved = classify_state(text, profile_selectors)
        if resolved is not None or button_texts:
            state_label, button_bounds, state = text, bounds, resolved
            break

    if button_bounds is None:
        return None

    # Everything but the button: the name first (topmost), then the social context,
    # which is optional — many rows have none.
    others = [(text, bounds) for text, bounds in texts if bounds != button_bounds]
    others.sort(key=lambda item: item[1][1])
    if not others:
        return None

    cell_bounds = parse_bounds(cell.get("bounds") or "")
    return {
        "label": others[0][0],
        "state": state,
        "state_label": state_label,
        "social_context": others[1][0] if len(others) > 1 else "",
        "follow_point": center(button_bounds),
        # The row body is what gets tapped to open the profile, when the @handle and
        # the profile data are wanted rather than a blind follow from the list.
        "row_point": center(others[0][1]),
        "row_top": cell_bounds[1] if cell_bounds else others[0][1][1],
    }


def _rows_from_geometry(nodes, profile_selectors, classify_state,
                        screen_height: Optional[int],
                        screen_width: Optional[int]) -> List[Dict[str, Any]]:
    """Fallback: rebuild the rows by vertical proximity, without a cell.

    Kept for the layouts that do not render ``igds_people_cell``: losing the whole
    zone on an unknown layout would be worse than reading it heuristically.
    """
    rows: List[Dict[str, Any]] = []
    pitch = int((screen_height or 2400) * _ROW_PITCH_RATIO)
    band = max(pitch // 2, 1)

    # The button lives in the RIGHT COLUMN, the name and context on the left. Without
    # this bound, an account actually named "Follow" reads as a button and fabricates
    # a row that does not exist. Expressed as a fraction of the width, never pixels.
    right_column = (screen_width or 1080) * 0.55
    buttons = [(text, bounds) for text, bounds in nodes
               if bounds[0] >= right_column
               and classify_state(text, profile_selectors) is not None]

    for state_label, button_bounds in buttons:
        state = classify_state(state_label, profile_selectors)
        button_y = vertical_center(button_bounds)

        # The texts of THIS row: same vertical band, and not the button itself.
        siblings = [
            (text, bounds) for text, bounds in nodes
            if bounds is not button_bounds
            and abs(vertical_center(bounds) - button_y) <= band
            and bounds[0] < right_column
        ]
        siblings.sort(key=lambda item: item[1][1])
        if not siblings:
            continue

        rows.append({
            "label": siblings[0][0],
            "state": state,
            "state_label": state_label,
            "social_context": siblings[1][0] if len(siblings) > 1 else "",
            "follow_point": center(button_bounds),
            "row_point": center(siblings[0][1]),
            "row_top": button_bounds[1],
        })
    return rows


def parse_notification_suggestions(
    root,
    header_texts: Sequence[str],
    profile_selectors,
    classify_state: Callable[[str, Any], Optional[str]],
    screen_height: Optional[int] = None,
    screen_width: Optional[int] = None,
    header_resource_id: Optional[str] = None,
    row_resource_id: Optional[str] = None,
    button_resource_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Suggestion rows visible below the header, top to bottom.

    Each dict exposes ``label``, ``state``, ``state_label``, ``social_context``,
    ``follow_point`` (the button) and ``row_point`` (the row body, tapped to open the
    profile).

    Two paths, in this order: by CELL (``row_resource_id``) when the surface exposes
    one — the only reliable way not to confuse a suggestion with a notification that
    also carries a follow button — then by geometry as a fallback.
    """
    if root is None:
        return []

    header_y = find_suggestions_header_y(root, header_texts, header_resource_id)
    if header_y is None:
        return []

    if row_resource_id:
        cells = []
        for node in root.iter("node"):
            if not _has_id(node, row_resource_id):
                continue
            bounds = parse_bounds(node.get("bounds") or "")
            # Strictly BELOW the header: above it are the notifications.
            if bounds and bounds[1] > header_y:
                cells.append((bounds[1], node))
        if cells:
            cells.sort(key=lambda item: item[0])
            rows = [_row_from_cell(node, profile_selectors, classify_state, button_resource_id)
                    for _top, node in cells]
            return [row for row in rows if row]

    nodes = [(text, bounds) for _node, text, bounds in iter_text_nodes(root)
             if bounds[1] > header_y]
    rows = _rows_from_geometry(nodes, profile_selectors, classify_state,
                               screen_height, screen_width)
    rows.sort(key=lambda row: row["row_top"])
    return rows


def followable_suggestions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The rows that are actually to be followed.

    Same rule as from the feed: only a button whose state is exactly 'follow' is
    tapped. A 'follow_back' belongs to the follow-back flow, a 'following' is done.
    """
    return [row for row in rows if row.get("state") == "follow" and row.get("follow_point")]


__all__ = [
    "find_suggestions_header_y",
    "iter_text_nodes",
    "parse_notification_suggestions",
    "followable_suggestions",
]
