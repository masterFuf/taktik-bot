"""Reading the TEXT of the comments under a post.

Instagram renders its comments with **Litho**, so the bodies are NOT in the accessibility
hierarchy: an XML dump of an open thread shows the row ViewGroups, the usernames, the Reply
buttons and the hearts, but every comment's text is missing. Reading it takes a second,
different source — `adb shell dumpsys activity top`, whose Litho dump does carry
`row_comment_textview_comment`.

The two sources answer different questions and are used together:

  * the XML says **who is on screen right now** (the Litho dump also lists recycled rows
    that have scrolled away, and replying to one of those would reply to the wrong person);
  * the Litho dump says **what each of them wrote**.

This is the mechanism the standalone Smart Comment bridge proved in production; it lives in
core so the in-thread reply keeps using it once that bridge is gone.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell_process
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS

# A comment body carries no attribute saying "this is a body", so each field is located by
# its Litho node name and the records are rebuilt from the ORDER the fields appear in.
_LITHO_PATTERNS = {
    "username": re.compile(r'text="([\w][\w.]{0,29})"\s+props="\{"synthetic":true\}"'),
    "comment": re.compile(r'row_comment_textview_comment\s+text="([^"]+)"'),
    "likes": re.compile(r'row_comment_textview_like_count\s+text="(\d+)"'),
}
_USERNAME_RE = re.compile(r"^[\w][\w.]{0,29}$")
_MENTION_RE = re.compile(r"@([\w][\w.]{0,29})")


def parse_litho_comments(dumpsys_output: str) -> List[Dict[str, Any]]:
    """Comment records from a `dumpsys activity top` dump.

    Returns ``[{username, text, likes, is_reply, parent_username}]``. A body that opens with
    an @mention is a reply to that person, which is how a nested reply is told apart from a
    top-level comment without walking the tree.
    """
    events = []
    for name, pattern in _LITHO_PATTERNS.items():
        for match in pattern.finditer(dumpsys_output or ""):
            events.append((match.start(), name, match.group(1)))
    events.sort(key=lambda item: item[0])

    comments: List[Dict[str, Any]] = []
    current_username: Optional[str] = None

    for _, kind, value in events:
        if kind == "username":
            current_username = value
        elif kind == "likes":
            if comments and value and int(value) > 0:
                comments[-1]["likes"] = int(value)
        elif kind == "comment":
            text = (value or "").strip()
            if not current_username or not text:
                continue
            mention = _MENTION_RE.match(text)
            comments.append({
                "username": current_username,
                "text": text,
                "likes": 0,
                "is_reply": bool(mention),
                "parent_username": mention.group(1) if mention else None,
            })
            current_username = None  # each username labels exactly one body

    return comments


def extract_visible_comment_usernames(xml: str) -> Set[str]:
    """Lower-cased usernames currently on screen, from a hierarchy dump."""
    visible: Set[str] = set()
    if not xml:
        return visible
    try:
        root = ET.fromstring(xml)
    except Exception:
        return visible

    recycler = _find_comments_recycler(root) or root
    for elem in recycler.iter():
        text = (elem.get("text") or "").strip()
        if _looks_like_username_button(elem.get("class") or "", text):
            visible.add(text.lower())
        # The avatar next to a comment spells the owner out ("Go to <user>'s profile"), which
        # still identifies the row when its username button is clipped.
        desc = (elem.get("content-desc") or elem.get("content-description") or "").strip()
        for pattern in POST_COMMENTS_SELECTORS.profile_content_description_patterns:
            match = re.search(pattern, desc)
            if match:
                visible.add(match.group(1).lower())
    return visible


def resolve_device_serial(device) -> str:
    """The adb serial behind `device`, needed for the Litho dump.

    Looked up on the object and through the facade wrappers, so a caller never has to
    thread a serial it already holds indirectly.
    """
    for candidate in (device, getattr(device, "_device", None), getattr(device, "device", None)):
        if candidate is None:
            continue
        serial = getattr(candidate, "serial", None)
        if serial:
            return str(serial)
    return ""


def read_visible_comments(device, device_id: str = "") -> List[Dict[str, Any]]:
    """The comments visible on screen right now, WITH their text.

    Litho-only records (rows recycled off-screen) are dropped: acting on one would target
    whoever happens to be scrolled away. Returns [] rather than raising when either source
    is unavailable — a caller that cannot read the thread simply has nothing to reply to.
    """
    device_id = device_id or resolve_device_serial(device)
    if not device_id:
        logger.debug("[comments] no adb serial — cannot read the Litho dump")
        return []

    try:
        xml = device.dump_hierarchy()
    except Exception as exc:
        logger.debug(f"[comments] hierarchy dump failed: {exc}")
        return []

    on_screen = extract_visible_comment_usernames(xml or "")

    try:
        result = run_adb_shell_process(
            device_id, ["dumpsys", "activity", "top"],
            timeout=10, encoding="utf-8", errors="replace",
        )
        dumpsys = result.stdout or ""
    except Exception as exc:
        logger.debug(f"[comments] dumpsys activity top failed: {exc}")
        return []

    comments = parse_litho_comments(dumpsys)
    if on_screen:
        comments = [c for c in comments if c["username"].lower() in on_screen]
    return comments


def _find_comments_recycler(root):
    key = POST_COMMENTS_SELECTORS.comments_list_resource_key
    for elem in root.iter():
        if key in (elem.get("resource-id") or ""):
            return elem
    return None


def _looks_like_username_button(node_class: str, text: str) -> bool:
    return (
        node_class == POST_COMMENTS_SELECTORS.button_class_name
        and bool(text)
        and bool(_USERNAME_RE.match(text))
        and text.lower() not in POST_COMMENTS_SELECTORS.ignored_username_tokens
    )


__all__ = [
    "parse_litho_comments",
    "extract_visible_comment_usernames",
    "read_visible_comments",
    "resolve_device_serial",
]
