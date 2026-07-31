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
