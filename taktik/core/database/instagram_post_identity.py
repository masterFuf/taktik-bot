"""How we identify a post across tables, without paying for it.

Instagram's mobile UI never hands us a post id: the only stable, FREE signal we can read
from an opened post is its author plus the author's own caption. `build_post_ref` turns
that pair into a short key shared by `posted_comments` (group the comments left on one
post) and `post_analysis` (reuse a vision analysis we already paid for).

The shareable URL would be a perfect key, but it costs a share-sheet round trip per post
(see CommentAction._attach_post_url) — far too expensive to gate a cache on.

Known limits, deliberate:
  - No caption -> the ref degrades to the author alone, which COLLIDES across all of that
    author's captionless posts. Callers that use the ref as a cache key must therefore
    require a discriminating caption (see `is_discriminating_post_ref`).
  - One author reusing the exact same caption on two posts yields one ref. Rare, and the
    consequence is soft (a slightly-off description), but it is a real false-hit case.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Tuple
from urllib.parse import urlsplit

# Below this many characters a caption is too weak to identify a post on its own
# ("Merci ❤️", "✨", an emoji row are all plausible duplicates across posts).
MIN_DISCRIMINATING_CAPTION = 15

# URL path markers that precede a post's shortcode, mapped to the post type they imply.
_POST_URL_KINDS = {"p": "post", "reel": "reel", "reels": "reel", "tv": "post"}


def split_post_url(post_url: Optional[str]) -> Optional[Tuple[str, str]]:
    """The (kind, shortcode) carried by an Instagram post URL, or None.

    Accepts every shape the app hands out: ``/p/<code>/``, ``/reel/<code>/``,
    ``/reels/<code>/``, ``/tv/<code>/``, the web form ``/<user>/p/<code>/``, with or
    without scheme, trailing slash, query (``?igsh=...``) or fragment.
    """
    raw = (post_url or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    segments = [s for s in urlsplit(raw).path.split("/") if s]
    for marker, code in zip(segments, segments[1:]):
        kind = _POST_URL_KINDS.get(marker.lower())
        if kind and code:
            return kind, code
    return None


def canonical_post_url(post_url: Optional[str]) -> Optional[str]:
    """One URL per post, whatever copy of it we were given.

    A share-sheet link carries a per-copy ``?igsh=`` token, so two copies of the SAME post
    never compare equal as-is; keyed raw, the catalogue would hold one row per copy. The
    canonical form keeps only what identifies the post: ``https://www.instagram.com/p/<code>/``
    (``reels`` folds into ``reel``). Returns None when no shortcode can be read.
    """
    parts = split_post_url(post_url)
    if parts is None:
        return None
    kind, code = parts
    segment = "reel" if kind == "reel" else "p"
    return f"https://www.instagram.com/{segment}/{code}/"


def post_shortcode_from_url(post_url: Optional[str]) -> Optional[str]:
    """The shortcode inside a post URL, or None."""
    parts = split_post_url(post_url)
    return parts[1] if parts else None


def build_post_ref(post_author: Optional[str], post_caption: Optional[str]) -> Optional[str]:
    """A cheap, stable-ish identity for a post: author + short hash of its caption.

    Two comments left on the SAME post therefore carry the same ref, which is what makes
    it useful for grouping. Falls back to the author alone when the post has no caption —
    weaker, but still better than nothing for GROUPING (never use that form as a cache key,
    cf. `is_discriminating_post_ref`).
    """
    author = (post_author or "").strip().lstrip("@").lower()
    caption = (post_caption or "").strip()
    if not author and not caption:
        return None
    if not caption:
        return author or None
    digest = hashlib.sha1(caption.encode("utf-8", "ignore")).hexdigest()[:12]
    return f"{author}:{digest}" if author else digest


def is_discriminating_post_ref(post_caption: Optional[str]) -> bool:
    """Whether a ref built from this caption may be used as a CACHE key.

    A cache MISS only costs the call we would have made anyway; a wrong HIT serves another
    post's analysis. So the rule fails closed: no caption, or one too short to tell two
    posts apart, means "do not cache".
    """
    return len((post_caption or "").strip()) >= MIN_DISCRIMINATING_CAPTION


__all__ = [
    "build_post_ref",
    "is_discriminating_post_ref",
    "MIN_DISCRIMINATING_CAPTION",
    "split_post_url",
    "canonical_post_url",
    "post_shortcode_from_url",
]
