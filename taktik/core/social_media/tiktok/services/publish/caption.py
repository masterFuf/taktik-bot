"""Reusable TikTok publish caption formatting."""

from __future__ import annotations

import re
from typing import Iterable


MAX_TIKTOK_HASHTAGS = 5
HASHTAG_TOKEN_RE = re.compile(r"#[A-Za-z0-9_\u00C0-\u024F]+")
HASHTAG_CLEAN_RE = re.compile(r"[^A-Za-z0-9_\u00C0-\u024F]")


def build_caption(caption: str, hashtags: Iterable[str] | None) -> str:
    """Build the final TikTok caption text from plain text and clean hashtags."""
    parts: list[str] = []
    clean_caption = (caption or "").strip()
    clean_hashtags = [
        str(tag).lstrip("#").strip()
        for tag in (hashtags or [])
        if str(tag).lstrip("#").strip()
    ]

    if clean_caption:
        parts.append(clean_caption)
    if clean_hashtags:
        parts.append(" ".join(f"#{tag}" for tag in clean_hashtags))

    return "\n".join(parts)


def sanitize_caption_and_hashtags(
    caption: str,
    hashtags,
    max_hashtags: int = MAX_TIKTOK_HASHTAGS,
) -> tuple[str, list[str], int]:
    """Normalize TikTok caption and hashtags while preserving simple behavior.

    Returns:
        `(caption_without_hashtags, selected_hashtags, dropped_count)`.
    """
    caption = caption or ""
    explicit_hashtags = _coerce_hashtag_input(hashtags)
    caption_hashtags = HASHTAG_TOKEN_RE.findall(caption)
    clean_hashtags: list[str] = []

    for raw in [*caption_hashtags, *explicit_hashtags]:
        tag = HASHTAG_CLEAN_RE.sub("", str(raw).lstrip("#").strip()).lower()
        if tag and tag not in clean_hashtags:
            clean_hashtags.append(tag)

    selected = clean_hashtags[:max_hashtags]
    stripped_caption = HASHTAG_TOKEN_RE.sub("", caption)
    stripped_caption = re.sub(r"[ \t]{2,}", " ", stripped_caption)
    stripped_caption = re.sub(r"[ \t]+\n", "\n", stripped_caption)
    stripped_caption = re.sub(r"\n{3,}", "\n\n", stripped_caption).strip()

    return stripped_caption, selected, max(0, len(clean_hashtags) - len(selected))


def _coerce_hashtag_input(hashtags) -> list[str]:
    if hashtags is None:
        return []
    if isinstance(hashtags, list):
        return [str(tag) for tag in hashtags]
    return str(hashtags).replace(",", " ").split()
