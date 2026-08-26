"""Everything the post catalogue needs about the post OPEN on screen, read in one place.

`social_posts` stores one card per post: who published it, how it is doing (likes, comments),
what it says, and the URL a `post_url` workflow can deep-link to. Those four reads already
existed, each in its own owner — counters in `InstagramUIExtractors`, the framed post's
header/caption in `PostReadingMixin`, the URL in `post_navigation` — but nothing composed
them, so every caller that wanted "the post" re-spelled the composition. This module is that
composition, used by the profile-posts scan AND by the Lab action `post.read_card`, so what
the Lab shows is literally what the scan writes.

The share-sheet round trip (the URL) is the expensive step: `with_url=False` reads
everything else, which is enough to recognise a post the catalogue already holds by its
`post_ref` and skip the sheet.

All functions take `device` and `logger` — no class dependency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from taktik.core.database.instagram_post_identity import build_post_ref, canonical_post_url

from ...ui.extractors import InstagramUIExtractors, username_from_media_label
from ...ui.selectors.shell.screen_state import DETECTION_SELECTORS
from ...ui.selectors.surfaces.post import POST_DETAIL_SELECTORS
from ..core.caption_hygiene import clean_post_caption
from .detection import is_reel_post
from .post_navigation import get_post_url_from_share


@dataclass
class PostCard:
    """What was read on the open post. `None` means "could not be read", never zero."""

    author: Optional[str]
    is_reel: bool
    likes_count: Optional[int]
    comments_count: Optional[int]
    caption: Optional[str]
    posted_at_label: Optional[str]
    post_url: Optional[str]
    post_ref: Optional[str]
    #: Whether both counters came from ONE element (guaranteed to describe the same post).
    counters_atomic: bool

    def as_dict(self) -> dict:
        return asdict(self)


def read_open_post_card(
    device,
    logger=None,
    *,
    ui_extractors=None,
    scroll_actions=None,
    with_url: bool = True,
    author_hint: Optional[str] = None,
) -> PostCard:
    """Read the card of the post currently open in the viewer.

    `ui_extractors` / `scroll_actions` are the production instances when the caller has them
    (a workflow, the Lab bundle); built on the spot otherwise. `author_hint` is the account
    whose grid the post was opened from: when the author cannot be read on screen, the post
    is still that account's, so the hint fills in rather than losing the row.
    """
    extractors = ui_extractors or InstagramUIExtractors(device)
    is_reel = is_reel_post(device, logger)

    likes, comments, atomic = _read_counters(extractors, is_reel, logger)

    if is_reel:
        author, caption, date_label = _read_reel_context(device, logger)
    else:
        author, caption, date_label = _read_framed_context(device, scroll_actions, logger)
        if author is None and caption is None:
            # A photo opened from a grid is framed like a feed post; when no header is visible
            # the viewer is in another layout, and the reel selectors are the next best read.
            author, caption, date_label = _read_reel_context(device, logger)

    if not author and author_hint:
        author = author_hint.strip().lstrip("@").lower() or None

    post_url = read_open_post_url(device, logger) if with_url else None

    return PostCard(
        author=author,
        is_reel=is_reel,
        likes_count=likes,
        comments_count=comments,
        caption=caption,
        posted_at_label=date_label,
        post_url=post_url,
        post_ref=build_post_ref(author, caption),
        counters_atomic=atomic,
    )


def read_open_post_url(device, logger=None) -> Optional[str]:
    """The open post's shareable URL in canonical form, or None.

    The expensive read (share sheet, copy link, read back), kept separate so a caller that
    recognised the post by its `post_ref` can skip it.
    """
    raw_url = get_post_url_from_share(device, logger)
    post_url = canonical_post_url(raw_url)
    if raw_url and not post_url and logger:
        logger.warning(f"read_open_post_url: share URL without a shortcode: {raw_url!r}")
    return post_url


def _read_counters(extractors, is_reel: bool, logger=None):
    """(likes, comments, atomic). The atomic read first: it takes both numbers from ONE
    element, so they cannot come from two different posts. The separate extractors answer 0
    when they find nothing, which is not a measurement — a double zero on that path is
    reported as unreadable rather than written over a value the catalogue already holds."""
    atomic = None
    try:
        atomic = extractors.extract_post_stats_atomic()
    except Exception as exc:
        if logger:
            logger.debug(f"read_open_post_card: atomic counters failed: {exc}")
    if atomic:
        return atomic.get("likes"), atomic.get("comments"), True

    try:
        likes = extractors.extract_likes_count_from_ui(is_reel=is_reel)
        comments = extractors.extract_comments_count_from_ui(is_reel=is_reel)
    except Exception as exc:
        if logger:
            logger.debug(f"read_open_post_card: counters failed: {exc}")
        return None, None, False
    if not likes and not comments:
        return None, None, False
    return likes, comments, False


def _read_framed_context(device, scroll_actions, logger=None):
    """(author, caption, date_label) of a framed feed-style post, through the production
    reader the AI comment grounds on. The header content-desc carries author and date in one
    sentence; the author is its first word, the rest is kept as the date label."""
    if scroll_actions is None:
        from ...actions.atomic.scroll import ScrollActions
        scroll_actions = ScrollActions(device)
    try:
        ctx = scroll_actions.framed_post_context()
    except Exception as exc:
        if logger:
            logger.debug(f"read_open_post_card: framed context failed: {exc}")
        return None, None, None
    if not ctx:
        return None, None, None

    author = (ctx.get("author") or "").strip().lstrip("@").lower() or None
    header = (ctx.get("header_desc") or "").strip()
    date_label = header.split(" ", 1)[1].strip() if author and " " in header else (header or None)
    cleaned = clean_post_caption(ctx.get("caption_text"), author_hint=author)
    return author, (cleaned.text or None), (date_label or None)


def _read_reel_context(device, logger=None):
    """(author, caption, date_label) of a reel through the catalogue's reel selectors, with
    the media label as author fallback (it is translated, hence read language-agnostically)."""
    author = None
    for selector in POST_DETAIL_SELECTORS.reel_author_username_selectors:
        try:
            element = device.xpath(selector)
            if not element.exists:
                continue
            info = element.info
            text = element.get_text() or info.get("contentDescription") or info.get("text") or ""
            if text.strip():
                author = text.strip().lstrip("@").lower()
                break
        except Exception:
            continue

    if not author:
        sources = list(DETECTION_SELECTORS.carousel_selectors)
        sources.append(POST_DETAIL_SELECTORS.photo_imageview_selector)
        for selector in sources:
            try:
                for element in device.xpath(selector).all():
                    author = username_from_media_label(element.info.get("contentDescription", ""))
                    if author:
                        break
            except Exception:
                continue
            if author:
                break

    caption = None
    for selector in POST_DETAIL_SELECTORS.reel_caption_selectors:
        try:
            element = device.xpath(selector)
            if not element.exists:
                continue
            text = element.info.get("contentDescription", "") or element.get_text() or ""
            if text.strip():
                caption = clean_post_caption(text, author_hint=author).text or None
                break
        except Exception:
            continue

    # The date shares the caption component; it is the text that is not the caption and
    # carries a digit. Best effort — a reel without a readable date keeps its row.
    date_label = None
    for selector in POST_DETAIL_SELECTORS.reel_date_selectors:
        try:
            query = device.xpath(selector)
            if not query.exists:
                continue
            for element in query.all():
                text = (element.info.get("contentDescription", "") or element.get_text() or "").strip()
                if text and text != caption and any(ch.isdigit() for ch in text) and len(text) <= 40:
                    date_label = text
                    break
            if date_label:
                break
        except Exception:
            continue

    return author, caption, date_label


__all__ = ["PostCard", "read_open_post_card", "read_open_post_url"]
