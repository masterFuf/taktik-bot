"""Data-only post context extraction helpers for Smart Comment."""

import re
import xml.etree.ElementTree as ET

from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS


def derive_author_and_caption(full_text: str, author_username: str = "") -> tuple[str, str]:
    """Derive the author username and caption from Instagram's combined caption text."""
    author = author_username
    if not author and full_text:
        first_space = full_text.find(" ")
        if first_space > 0:
            candidate = full_text[:first_space].strip()
            if re.match(r"^[\w][\w.]{0,29}$", candidate):
                author = candidate

    if author and full_text.startswith(author):
        caption = full_text[len(author):].strip()
    else:
        caption = full_text

    caption = re.sub(POST_DETAIL_SELECTORS.caption_tail_pattern, "", caption)
    return author, caption


def extract_post_date_from_xml(xml: str) -> str:
    """Extract the first matching post date from a hierarchy XML dump."""
    if not xml:
        return ""

    root = ET.fromstring(xml)
    for elem in root.iter():
        text = (elem.get("text", "") or "").strip()
        content_desc = (elem.get("content-desc", "") or "").strip()
        cls = elem.get("class", "") or ""
        if (
            cls == POST_DETAIL_SELECTORS.text_view_class_name
            and text
            and re.match(POST_DETAIL_SELECTORS.post_date_pattern, text)
        ):
            return text
        if content_desc and re.match(POST_DETAIL_SELECTORS.post_date_pattern, content_desc):
            return content_desc
    return ""


__all__ = ["derive_author_and_caption", "extract_post_date_from_xml"]
