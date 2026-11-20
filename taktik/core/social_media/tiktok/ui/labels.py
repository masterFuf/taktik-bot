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

from taktik.core.shared.text import normalize_ui_label, strip_layout_marks
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.locales import L_in, active_locale, available_locales
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.media import VIDEO_MEDIA_SELECTORS


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


#: What separates the caption from the translation link written after it ("plus | Voir la traduction").
_TRANSLATE_SEPARATOR = "|"


def caption_as_displayed(text: str) -> str:
    """The caption text without what TikTok writes around it to lay it out.

    Measured on 47.0.3 (Pixel 6a, French, 2026-11-20): word joiners (U+2060) between the ellipsis
    and « plus », and around « | Voir la traduction », a link written in the caption's own text
    after its last word. The same version also shows captions without either. Both go: a joiner
    is a layout mark, the link is not the author's text.
    """
    shown = strip_layout_marks(text).rstrip()
    for label in VIDEO_MEDIA_SELECTORS.description_translate_labels:
        if not label or not shown.endswith(label):
            continue
        head = shown[: -len(label)]
        # After a cut caption: « plus | Voir la traduction » ; after a whole one: two spaces.
        if head.rstrip().endswith(_TRANSLATE_SEPARATOR):
            return head.rstrip()[: -len(_TRANSLATE_SEPARATOR)].rstrip()
        if head != head.rstrip():
            return head.rstrip()
    return shown


def _more_suffix_start(text: str, labels=None) -> Optional[int]:
    """Where the ellipsis and "more" word TikTok appends to a cut caption begin, or None, in
    `caption_as_displayed(text)`.

    The space between the two varies ("… plus", "…plus"), and so does the ellipsis ("…", "...").
    """
    tail = caption_as_displayed(text)
    if labels is None:
        labels = VIDEO_MEDIA_SELECTORS.description_more_labels
    for label in labels or []:
        if label and tail.endswith(label):
            head = tail[: -len(label)].rstrip()
            for ellipsis in ("…", "..."):
                if head.endswith(ellipsis):
                    return len(head) - len(ellipsis)
    return None


def is_truncated_description(text: str) -> bool:
    """True when TikTok cut the caption and offers to show the rest."""
    return _more_suffix_start(text) is not None


#: The languages whose cut caption the bot taps open. A language is listed once a run has proven the tap:
#: French on 2026-11-20 (47.0.3, Pixel 6a, 14 videos), behind the two guards below (the start of the
#: first line, only on plain text; the screen read again, a tap that left the video taken back).
#: English was tapped before them; on 47 it is not proven on a phone.
TAP_OPEN_CAPTION_LOCALES = ("en", "fr")

#: The caption is one TextView whose "…more" / "… plus" is the end of its own text, not a node, and
#: its hashtags and mentions are links inside that text: a tap at the centre can open one. The bot
#: taps the start of the first line (`caption_tap_zone`), and only when the caption starts with this
#: many characters of plain text (no "#", no "@"). Measured on 47.0.3 (Pixel 6a, 2026-11-20): the node
#: is 838 px wide for about 45 characters a line (95 on two lines), some 19 px a character, so the
#: zone (`CAPTION_TAP_WIDTH` of the width) covers about 7 characters, under this threshold.
CAPTION_PLAIN_START_CHARS = 12
CAPTION_TAP_WIDTH = 0.15
#: The first line of the node: a cut caption shows two lines (100 px for two lines of 50 measured),
#: and a fifth of the node stays inside the first line up to five lines.
CAPTION_TAP_HEIGHT = 0.2
_LINK_MARKS = ("#", "@")


def _starts_with_post_link(shown: str) -> bool:
    """« Publication 1 | … »: a link to a photo post, its word in the locales, then a number and "|"."""
    words = shown.replace("\u00a0", " ").split(" ", 3)
    return (len(words) >= 3 and words[0] in VIDEO_MEDIA_SELECTORS.caption_link_prefixes
            and words[1].isdigit() and words[2] == _TRANSLATE_SEPARATOR)


def caption_starts_plain(text: str) -> bool:
    """Does the caption start with plain text, where a tap opens no link?"""
    shown = caption_as_displayed(text).lstrip()
    start = shown[:CAPTION_PLAIN_START_CHARS]
    return (len(start) == CAPTION_PLAIN_START_CHARS and not any(mark in start for mark in _LINK_MARKS)
            and not _starts_with_post_link(shown))


def caption_tap_zone(bounds):
    """The start of the caption node's first line, from its bounds (left, top, right, bottom)."""
    left, top, right, bottom = bounds
    return (left, top, left + max(1, int((right - left) * CAPTION_TAP_WIDTH)),
            top + max(1, int((bottom - top) * CAPTION_TAP_HEIGHT)))


def same_caption_opened(cut: str, shown: Optional[str]) -> bool:
    """Is `shown`, read after the tap, the caption that was `cut`, still on its video?"""
    head = strip_more_suffix(cut)[:CAPTION_PLAIN_START_CHARS]
    return bool(shown) and bool(head) and caption_as_displayed(shown).startswith(head)


def is_expandable_description(text: str) -> bool:
    """True when the caption is cut AND its language is one the bot taps open."""
    active = active_locale()
    langs = [active] if active else available_locales()
    labels = [label for lang in langs if lang in TAP_OPEN_CAPTION_LOCALES
              for label in L_in(lang, "video_media.description_more_labels")]
    return _more_suffix_start(text, labels) is not None


def strip_more_suffix(text: str) -> str:
    """The caption as displayed, without the ellipsis and "more" word of a cut caption."""
    shown = caption_as_displayed(text)
    start = _more_suffix_start(shown)
    return shown if start is None else shown[:start]
