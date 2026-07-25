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
from typing import Optional

# Below this many characters a caption is too weak to identify a post on its own
# ("Merci ❤️", "✨", an emoji row are all plausible duplicates across posts).
MIN_DISCRIMINATING_CAPTION = 15


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


__all__ = ["build_post_ref", "is_discriminating_post_ref", "MIN_DISCRIMINATING_CAPTION"]
