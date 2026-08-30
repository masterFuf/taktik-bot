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

from taktik.core.shared.text import fold_for_match

_PLATFORM = "tiktok"

#: Everything an XML dump can mangle or a UI can pad: the fingerprint must survive all of it.
#: Astral characters (emoji) come back as pairs of dots on some reads and intact on others, so the
#: safest fold is to drop everything that is not a letter or a digit.
_KEEP = re.compile(r"[^0-9a-z]+")


def _fold(text: str) -> str:
    """The shared fold, with the leading `@` taken off first.

    One fold for the author and the caption both, and the same one the conversation guard and the
    niche matcher use: anything a dump can mangle or a UI can pad has to disappear before hashing,
    or the same post read twice keys twice.
    """
    return fold_for_match((text or "").strip().lstrip("@"))


def _fingerprint(caption: Optional[str]) -> str:
    """A short, stable digest of a caption — or `nocaption` when there is none.

    Accent-folded and stripped of everything but letters and digits BEFORE hashing, because the
    same caption read twice does not come back byte-identical: the dump eats emoji into dots, and
    a trailing space or a curly apostrophe is enough to change a raw hash.
    """
    folded = _fold(caption or "")
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

    Returns None when the author is unknown, and also when there is NEITHER a date NOR a caption:
    both cases would produce a key that several different posts answer to, which is worse than
    not storing them at all.
    """
    # Folded EXACTLY like the caption, and for the same reason. The first version kept the
    # author's punctuation, on the theory that a handle carries `.` and `_` that must not be
    # dropped. Measured on the FYP, that theory was wrong twice over: this surface renders a
    # DISPLAY NAME, not a handle -- the Lab run returned `charli d'amelio`, spaces and curly
    # apostrophe included -- and display names routinely carry emoji, which the dump turns into
    # two dots. Read intact once and mangled once, the same author gave two keys, which is the
    # exact failure the fingerprint exists to prevent.
    handle = _fold(author or "")
    if not handle:
        return None

    label = _KEEP.sub("", (posted_at_label or "").casefold())
    fingerprint = _fingerprint(caption)

    # An author alone is not a post. `tv_post_time` is absent from the FYP, so a caption-less
    # video there would key on nothing but its author -- and every caption-less video that author
    # ever posts would fold into that one row. Refusing is the same call as refusing a missing
    # author: not storing beats storing something that answers "already seen?" wrongly forever.
    if not label and fingerprint == "nocaption":
        return None

    return f"{_PLATFORM}:{handle}:{label or 'nodate'}:{fingerprint}"


__all__ = ["tiktok_post_key"]
