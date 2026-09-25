"""Reading TikTok UI LABELS — the language-dependent half of screen reading.

Selectors find a node; a label says what that node *is*. The two are different problems and
only the first one was centralised: the profile stat row is paired by position (resource-ids
``qfv``/``qfw``, language-neutral), but telling whether the value you hold is followers,
following or likes means reading the word next to it — and that word was compared against
hardcoded English (``'following' in label``). On a French phone none of the three matched, so
a scraped profile reported **zero followers, zero following, zero likes** without a single
error line.

Everything here compares through :func:`normalize_ui_label` (case, spacing and apostrophe
shapes folded) against the locale catalogues, so adding a language stays a catalogue edit.
"""

from typing import Iterable, Optional

from ....shared.text import normalize_ui_label
from .selectors.surfaces.profile import PROFILE_SELECTORS
from .selectors.surfaces.video.media import VIDEO_MEDIA_SELECTORS


def _matches(text: str, labels: Iterable[str]) -> bool:
    """True when ``text`` carries one of ``labels`` (both sides normalised)."""
    return any(normalize_ui_label(lbl) in text
               for lbl in (labels or []) if lbl and lbl.strip())


def classify_profile_stat_label(label: str) -> Optional[str]:
    """Turn a profile stat label into ``'following' | 'followers' | 'likes' | None``.

    ORDER MATTERS: "Following" contains "Follow" and, in several languages, the two
    subscription words share a stem — testing followers first would classify the following
    count as followers. Following is therefore tested first, exactly as the hardcoded
    English version did.
    """
    text = normalize_ui_label(label)
    if not text:
        return None
    if _matches(text, PROFILE_SELECTORS.stat_label_following):
        return "following"
    if _matches(text, PROFILE_SELECTORS.stat_label_followers):
        return "followers"
    if _matches(text, PROFILE_SELECTORS.stat_label_likes):
        return "likes"
    return None


def is_friends_button(text: str) -> bool:
    """True when a follow-state button says the relationship is MUTUAL ("Friends" / "Amis")."""
    normalized = normalize_ui_label(text)
    if not normalized:
        return False
    return _matches(normalized, PROFILE_SELECTORS.friends_button_labels)


def is_following_button(text: str) -> bool:
    """True when a follow-state button says WE follow them ("Suivis" / "Following").

    Distinct from :func:`is_friends_button`, which means the relationship is mutual. Reading a
    row's button is the cheapest way to learn a relationship -- the state IS the label -- and
    that is exactly why it has to go through the locale catalogue rather than an English literal.
    """
    normalized = normalize_ui_label(text)
    if not normalized:
        return False
    return _matches(normalized, PROFILE_SELECTORS.following_button_labels)


def is_follow_button(text: str) -> bool:
    """True when a follow-state button OFFERS to follow ("Suivre" / "Follow", "... en retour").

    Compared by EQUALITY, not containment like its two siblings: "Follow" is a prefix of
    "Following", so a containment test would read "we follow them" as "we do not". This is the
    label that proves an unfollow went through, so a loose match here would count taps as
    unfollows, the defect it exists to close.
    """
    normalized = normalize_ui_label(text)
    if not normalized:
        return False
    return any(normalized == normalize_ui_label(label)
               for label in (PROFILE_SELECTORS.follow_button_labels or []) if label and label.strip())


def classify_follow_button(text: str) -> Optional[str]:
    """What a row's follow-state button says: ``'friends' | 'following' | 'follow' | None``.

    Mutual first (a mutual follow is also a follow), then "we follow", then "we do not".
    """
    if is_friends_button(text):
        return "friends"
    if is_following_button(text):
        return "following"
    if is_follow_button(text):
        return "follow"
    return None


def _more_suffix_start(text: str) -> Optional[int]:
    """Where the ellipsis and "more" word TikTok appends to a cut caption begin, or None.

    The space between the two varies ("… plus", "…plus"), and so does the ellipsis ("…", "...").
    """
    tail = (text or "").rstrip()
    for label in VIDEO_MEDIA_SELECTORS.description_more_labels or []:
        if label and tail.endswith(label):
            head = tail[: -len(label)].rstrip()
            for ellipsis in ("…", "..."):
                if head.endswith(ellipsis):
                    return len(head) - len(ellipsis)
    return None


def is_truncated_description(text: str) -> bool:
    """True when TikTok cut the caption and offers to show the rest."""
    return _more_suffix_start(text) is not None


def strip_more_suffix(text: str) -> str:
    """The caption without the ellipsis and "more" word of a cut caption."""
    start = _more_suffix_start(text)
    return (text or "") if start is None else text[:start]
