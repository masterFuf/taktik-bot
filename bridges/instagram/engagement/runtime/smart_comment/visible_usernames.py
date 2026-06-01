"""Visible username extraction from Instagram comments XML."""

import re
import xml.etree.ElementTree as ET

from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


def extract_visible_comment_usernames(xml: str) -> set[str]:
    """Extract usernames visible in the comments RecyclerView from a hierarchy XML dump."""
    visible = set()
    if not xml:
        return visible

    root = ET.fromstring(xml)
    recycler = _find_comments_recycler(root) or root

    for elem in recycler.iter():
        tag_class = elem.get("class", "") or ""
        text = (elem.get("text", "") or "").strip()
        content_desc = (elem.get("content-description", "") or "").strip()

        if _looks_like_username_button(tag_class, text):
            visible.add(text.lower())

        for pattern in POST_COMMENTS_SELECTORS.profile_content_description_patterns:
            match = re.search(pattern, content_desc)
            if match:
                visible.add(match.group(1).lower())

    return visible


def _find_comments_recycler(root):
    for elem in root.iter():
        rid = elem.get("resource-id", "") or ""
        if POST_COMMENTS_SELECTORS.comments_list_resource_key in rid:
            return elem
    return None


def _looks_like_username_button(tag_class: str, text: str) -> bool:
    return (
        tag_class == POST_COMMENTS_SELECTORS.button_class_name
        and bool(text)
        and bool(re.match(r"^[\w][\w.]{0,29}$", text))
        and text.lower() not in POST_COMMENTS_SELECTORS.ignored_username_tokens
    )


__all__ = ["extract_visible_comment_usernames"]
