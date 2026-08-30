"""Is this video the kind we want more of?

Kept pure and away from the device on purpose. Deciding what a feed-training pass does to a video
is the part worth testing exhaustively, and it needs no screen at all -- only the three things the
video screen already gives: the caption, the sound label and the author's display name.

The folding is the same one `tiktok_post_key` uses, and for the same reason: what comes off a
screen does not come back byte-identical. The XML dump turns an emoji into two dots, captions
carry curly apostrophes, and a hashtag is written `#Fitness` as often as `fitness`. A matcher that
compares raw strings misses most of what it should catch.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence

from taktik.core.shared.text import fold_for_match


def _fold(text: Optional[str]) -> str:
    """The shared fold, with the separators kept as single spaces.

    Same rule as everywhere else -- accents, case and punctuation gone -- but words are kept
    apart here rather than run together, because this text is searched for keywords and not
    hashed. `#Fitness 🔥 du jour` becomes `fitness du jour`.
    """
    return " ".join(fold_for_match(part) for part in re.split(r"\s+", (text or "").strip()) if part).strip()


def normalise_keywords(keywords: Optional[Iterable[str]]) -> List[str]:
    """The keywords as the matcher will use them: folded, de-duplicated, empties dropped.

    Exposed rather than kept private so a caller can show the operator what their `#Fitness 🔥`
    actually became. A filter that silently rewrites its own input is a filter nobody can debug.
    """
    seen: List[str] = []
    for keyword in keywords or ():
        folded = _fold(keyword)
        if folded and folded not in seen:
            seen.append(folded)
    return seen


def matches_niche(
    fields: Sequence[Optional[str]],
    keywords: Optional[Iterable[str]],
) -> bool:
    """True when any keyword appears in any of the fields.

    Returns False when there are no keywords. That is the safe direction and it is worth being
    explicit about: with no niche declared, every video would otherwise be "in niche", and a
    training pass would spend a session sending positive signals about nothing in particular.

    Matching is on the FOLDED text, substring-wise. `fit` therefore matches `fitness`, which is
    wanted -- an operator typing a niche is naming a subject, not a token.
    """
    wanted = normalise_keywords(keywords)
    if not wanted:
        return False

    haystack = " ".join(_fold(field) for field in fields if field)
    if not haystack:
        return False
    return any(keyword in haystack for keyword in wanted)


def training_decision(
    fields: Sequence[Optional[str]],
    keywords: Optional[Iterable[str]],
    *,
    reject_off_niche: bool = True,
) -> str:
    """What to do with this video: `watch`, `skip`, or `reject`.

    - `watch`  the video is in niche. Stay on it; that is the positive signal.
    - `reject` it is not, and the pass is allowed to say so explicitly.
    - `skip`   it is not, but saying so is switched off -- swipe past and let the short watch time
               be the weak negative it already is.

    `reject_off_niche` defaults to on because the explicit signal is the only one TikTok treats as
    a statement. It is a switch rather than a constant because rejecting is visible in the app's
    own "not interested" history, and an operator may not want that on a client account.
    """
    if matches_niche(fields, keywords):
        return "watch"
    return "reject" if reject_off_niche else "skip"


__all__ = ["matches_niche", "normalise_keywords", "training_decision"]
