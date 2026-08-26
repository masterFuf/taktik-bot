"""Pure XML-dump parsers for the Instagram account suggestions.

- the suggestions carousel inserted in the feed, which is the entry point;
- the people discovery screen opened by its "See all" CTA, the list where the
  bulk follow and the qualified visit both happen.

No device access here: the functions take an lxml root (from ``dump_hierarchy``) and
return plain dicts, so they are testable from a captured dump. Resource-ids are matched
by SUBSTRING because some rows are rendered with a bare id and others fully qualified —
the same strategy as the notifications surface.

No UI signature is hardcoded: they come from the ``FEED_SUGGESTIONS_SELECTORS`` and
``DISCOVER_PEOPLE_SELECTORS`` catalogs, and the button state labels from
``PROFILE_SELECTORS.follow_state_labels_*`` through ``classify_follow_state`` — the
single source of truth, shared with the profile header.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from taktik.core.shared.device.ui_dump import parse_bounds


def _has_id(node, bare_id: str) -> bool:
    """True when the node resource-id contains ``bare_id``, bare or qualified."""
    return bare_id in (node.get("resource-id") or "")


def _find_descendant(node, bare_id: str):
    """First descendant, or the node itself, whose id contains ``bare_id``."""
    for descendant in node.iter():
        if _has_id(descendant, bare_id):
            return descendant
    return None


def _text_of(node) -> str:
    """Text of the node, or failing that of the first descendant carrying one.

    A compressed dump can put the text on a child TextView while the resource-id sits
    on the parent container.
    """
    if node is None:
        return ""
    text = (node.get("text") or "").strip()
    if text:
        return text
    for descendant in node.iter():
        value = (descendant.get("text") or "").strip()
        if value:
            return value
    return ""


def _label_of(node) -> str:
    """Text of the node, falling back on its ``content-desc`` (icon button)."""
    text = _text_of(node)
    if text:
        return text
    if node is None:
        return ""
    return (node.get("content-desc") or "").strip()


def _top_of(node) -> Optional[int]:
    bounds = parse_bounds(node.get("bounds") or "")
    return bounds[1] if bounds else None


# =============================================================================
# Suggestions carousel in the feed
# =============================================================================


def _labelled(node) -> str:
    """The node's visible label, from text or content-desc, normalised for comparison."""
    for attribute in ("text", "content-desc"):
        value = (node.get(attribute) or "").strip()
        if value:
            return value
    return ""


def _compose_header_and_cta(root, selectors):
    """The carousel's ``(title, cta_bounds)`` read from labels alone, or ``(None, None)``.

    The pairing rule is what makes a label-based match safe: the CTA must sit on the SAME ROW
    as the carousel's own header and to its RIGHT. A "See all" heading some other feed section
    has a different header on its row, so it cannot be mistaken for this one.
    """
    titles = {t.strip().lower() for t in getattr(selectors, "carousel_title_texts", []) if t}
    ctas = {c.strip().lower() for c in getattr(selectors, "carousel_cta_texts", []) if c}
    if not titles or not ctas:
        return None, None

    headers, buttons = [], []
    for node in root.iter("node"):
        label = _labelled(node)
        if not label:
            continue
        box = parse_bounds(node.get("bounds") or "")
        if not box:
            continue
        lowered = label.lower()
        if lowered in titles:
            headers.append((label, box))
        elif lowered in ctas:
            buttons.append(box)

    for label, header_box in headers:
        header_centre = (header_box[1] + header_box[3]) // 2
        for cta_box in buttons:
            on_same_row = cta_box[1] <= header_centre <= cta_box[3]
            to_the_right = cta_box[0] >= header_box[2]
            if on_same_row and to_the_right:
                return label, cta_box
    return None, None


def parse_feed_suggestions_carousel(root, selectors) -> Dict[str, Any]:
    """State of the suggestions carousel in the feed dump.

    Returns ``{present, title, cta_bounds, cards}`` — ``cta_bounds`` is the 4-tuple of
    the "See all" button, to be tapped to open the discovery screen, and ``cards`` the
    list of inline cards ``{name, follow_bounds, state_label}``.
    """
    result: Dict[str, Any] = {
        "present": False,
        "title": "",
        "cta_bounds": None,
        "cards": [],
    }
    if root is None:
        return result

    for node in root.iter("node"):
        if _has_id(node, selectors.carousel_container_id):
            result["present"] = True
            break

    for node in root.iter("node"):
        if _has_id(node, selectors.carousel_title_id):
            result["title"] = _label_of(node)
        elif _has_id(node, selectors.carousel_cta_id):
            result["cta_bounds"] = parse_bounds(node.get("bounds") or "")
        elif _has_id(node, selectors.card_container_id):
            name_node = _find_descendant(node, selectors.card_name_id)
            follow_node = _find_descendant(node, selectors.card_follow_button_id)
            if follow_node is None:
                continue
            result["cards"].append({
                "name": _label_of(name_node),
                "state_label": _label_of(follow_node),
                "follow_bounds": parse_bounds(follow_node.get("bounds") or ""),
            })

    # IG 442 rebuilt the block in Compose and kept NO resource-id: `netego_carousel_*` is
    # absent from the dump entirely, so everything above finds nothing and the only entry point
    # to the people-discovery screen became unreachable. The header and the CTA survive as two
    # labelled nodes on one row, which is the handle used here -- paired, never alone, because
    # "See all" by itself also heads other feed sections.
    if not result["cta_bounds"]:
        title, cta_bounds = _compose_header_and_cta(root, selectors)
        if cta_bounds:
            result["cta_bounds"] = cta_bounds
            if title and not result["title"]:
                result["title"] = title

    # A lone CTA with no container, which an alternative server layout serves, is enough
    # to consider the block present: it is what gets tapped.
    if result["cta_bounds"] and not result["present"]:
        result["present"] = True
    return result


# =============================================================================
# People discovery screen
# =============================================================================

def is_discover_people_screen(root, selectors) -> bool:
    """Surface proof: at least one recommendation row WITH its button.

    Deliberately structural rather than textual: the action-bar title is
    language-dependent, and the list stays recognisable once scrolled, when the
    titre a disparu du dump.
    """
    if root is None:
        return False
    has_row = False
    has_button = False
    for node in root.iter("node"):
        if _has_id(node, selectors.row_container_id):
            has_row = True
        elif _has_id(node, selectors.row_follow_button_id):
            has_button = True
        if has_row and has_button:
            return True
    return False


def read_screen_title(root) -> str:
    """Action-bar title, for observability (logs and reports)."""
    if root is None:
        return ""
    for node in root.iter("node"):
        if _has_id(node, "action_bar_title"):
            return _label_of(node)
    return ""


def parse_section_headers(root, selectors) -> List[Dict[str, Any]]:
    """Section headers of the list, ordered by vertical position."""
    headers: List[Dict[str, Any]] = []
    if root is None:
        return headers
    for node in root.iter("node"):
        if not _has_id(node, selectors.section_header_id):
            continue
        top = _top_of(node)
        headers.append({"label": _label_of(node), "top": top if top is not None else 0})
    headers.sort(key=lambda item: item["top"])
    return headers


def parse_suggestion_rows(root, selectors, profile_selectors,
                          classify_state) -> List[Dict[str, Any]]:
    """Lignes de suggestion visibles, de haut en bas.

    Each row is a subtree that already holds its label, its button and its social
    context, so no pairing by vertical proximity is needed.

    Each dict carries:

    - ``label``   : the text displayed, often the full name and sometimes the handle —
      this surface does NOT reliably expose the username;
    - ``state``   : the relationship state, read by ``classify_state`` on the button text;
    - ``section`` : the section header above the row, when visible;
    - ``follow_bounds`` / ``row_bounds`` / ``name_bounds`` : real geometry for a humanized
      tap. ``name_bounds`` aims at the NAME, so at opening the profile;
      ``follow_bounds`` aims at the button, so at following from the list.

    The "connect to Facebook" and "connect contacts" call-to-action rows are not
    suggestions and are ignored.
    """
    rows: List[Dict[str, Any]] = []
    if root is None:
        return rows

    headers = parse_section_headers(root, selectors)

    def _section_for(top: Optional[int]) -> str:
        if top is None:
            return ""
        label = ""
        for header in headers:
            if header["top"] <= top:
                label = header["label"]
            else:
                break
        return label

    for node in root.iter("node"):
        if not _has_id(node, selectors.row_container_id):
            continue
        if any(_has_id(node, connect_id) for connect_id in selectors.connect_row_ids):
            continue

        follow_node = _find_descendant(node, selectors.row_follow_button_id)
        if follow_node is None:
            continue

        name_node = _find_descendant(node, selectors.row_username_id)
        context_node = _find_descendant(node, selectors.row_social_context_id)
        row_bounds = parse_bounds(node.get("bounds") or "")
        state_label = _label_of(follow_node)

        rows.append({
            "label": _label_of(name_node),
            "state": classify_state(state_label, profile_selectors),
            "state_label": state_label,
            "social_context": _label_of(context_node),
            "section": _section_for(row_bounds[1] if row_bounds else None),
            "follow_bounds": parse_bounds(follow_node.get("bounds") or ""),
            "row_bounds": row_bounds,
        # Bounds of the NAME: this is where the tap opens the profile. The centre of the
        # whole row will not do — the follow button occupies its right side, so a tap
        # there would follow from the list instead.
            "name_bounds": parse_bounds(name_node.get("bounds") or "") if name_node is not None else None,
        })

    rows.sort(key=lambda row: row["row_bounds"][1] if row["row_bounds"] else 0)
    return rows


def followable_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sous-ensemble des lignes reellement a follow.

    Business rule: neither follow-back nor follow-request acceptance happens here — both
    belong to the notifications workflow. Only a button whose state is exactly 'follow'
    is tapped; the other states are left alone. A row with no usable label is ignored
    rather than tapped blindly.
    """
    return [row for row in rows
            if row.get("state") == "follow" and row.get("follow_bounds")]


__all__ = [
    "parse_feed_suggestions_carousel",
    "is_discover_people_screen",
    "read_screen_title",
    "parse_section_headers",
    "parse_suggestion_rows",
    "followable_rows",
]
