"""What identifies a TikTok post, when its link cannot.

Instagram's share link carries a per-copy `?igsh=` token; strip it and a stable canonical URL is
left, which is why `instagram_post_identity.canonical_post_url` is enough over there.

TikTok offers no such thing. Measured on device 2026-08-30, copying the same video's link four
times in a row gave four different URLs — `vm.tiktok.com/ZN8FUVpSM`, `ZN8FUWHSs`, `ZN8FUcEWh`,
`ZN8FUtvAr` — and a sweep of the whole accessibility tree of a video screen found no numeric video
id anywhere. The link is perfectly good for NAVIGATING and for sharing; it is only useless as an
identity. Keyed on it, one video would be stored once per visit, and "have we already engaged this
post?" would answer no forever.

So the identity is built from what the screen DOES show and does not change between visits:

    author + publication date + a fingerprint of the caption

All three were measured on the video screen: the author (`title`), the date (`tv_post_time`, e.g.
`· 06-12`) and the caption (`desc`). None of them alone would do — an author posts many videos, a
date repeats, and captions are sometimes empty — but together they identify a post as well as
anything available without opening it.

The caption is FINGERPRINTED rather than stored: a key belongs in an index, and a caption can run
to hundreds of characters with emoji the XML dump mangles differently between reads. The
fingerprint folds those away, so the same post read twice keys the same both times.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Optional

_PLATFORM = "tiktok"

#: Everything an XML dump can mangle or a UI can pad: the fingerprint must survive all of it.
#: Astral characters (emoji) come back as pairs of dots on some reads and intact on others, so the
#: safest fold is to drop everything that is not a letter or a digit.
_KEEP = re.compile(r"[^0-9a-z]+")


def _fingerprint(caption: Optional[str]) -> str:
    """A short, stable digest of a caption — or `nocaption` when there is none.

    Accent-folded and stripped of everything but letters and digits BEFORE hashing, because the
    same caption read twice does not come back byte-identical: the dump eats emoji into dots, and
    a trailing space or a curly apostrophe is enough to change a raw hash.
    """
    text = unicodedata.normalize("NFKD", (caption or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    folded = _KEEP.sub("", text)
    if not folded:
        return "nocaption"
    return hashlib.sha1(folded.encode("utf-8")).hexdigest()[:16]


def tiktok_post_key(
    author: Optional[str],
    posted_at_label: Optional[str] = None,
    caption: Optional[str] = None,
) -> Optional[str]:
    """The stable identity of one TikTok post, or None when there is not enough to identify it.

    `posted_at_label` is the date exactly as the screen writes it (`· 06-12`, `2026-6-12`, `3d`…),
    cleaned here rather than by the caller: it is a label, not a date, and parsing it into one
    would invent a precision the screen does not give.

    Returns None when the author is unknown — a key without an author would collide across
    accounts, which is worse than not storing the post.
    """
    # Accent-folded like the caption, but NOT stripped of punctuation: a handle may carry `.` and
    # `_`, and removing them would let `keo.2` and `keo2` collide into one post.
    handle = unicodedata.normalize("NFKD", (author or "").strip().lstrip("@").casefold())
    handle = "".join(char for char in handle if not unicodedata.combining(char))
    if not handle:
        return None
    label = _KEEP.sub("", (posted_at_label or "").casefold()) or "nodate"
    return f"{_PLATFORM}:{handle}:{label}:{_fingerprint(caption)}"


__all__ = ["tiktok_post_key"]
