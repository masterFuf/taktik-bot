"""Reading Instagram UI LABELS — the language-dependent half of screen reading.

Selectors find a node; a label says what that node *is*. A post's action bar is the clearest
case: the buttons are found generically (`all_button_nodes_selector`) and the counter that
FOLLOWS one of them is attributed by naming the button — which was done with hardcoded
English words. On a French phone `'Like' in "J'aime"` is false, so the counter was never
recognised and the likers list never opened. No exception, no error line: "I could not name
this button" and "there is no such button" produce the same empty result.

Everything here compares through :func:`normalize_ui_label` (case, spacing and apostrophe
shapes folded) against the locale catalogues, so adding a language stays a catalogue edit.
"""

from typing import Iterable, Optional

from ....shared.text import normalize_ui_label
from .selectors.shell.navigation import BUTTON_SELECTORS
from .selectors.support.text_reading import TEXT_READING_SELECTORS


def _matches(text: str, labels: Iterable[str]) -> bool:
    """True when ``text`` carries one of ``labels`` (both sides normalised)."""
    return any(normalize_ui_label(lbl) in text
               for lbl in (labels or []) if lbl and lbl.strip())


def classify_action_button(content_desc: str) -> Optional[str]:
    """Name a post action-bar button: ``'like' | 'comment' | 'share' | 'save' | None``.

    ``None`` for anything unrecognised — including the already-liked state ("Je n'aime
    plus"), which must never be read as the like button: that button sits next to the
    counter we then attribute, so a mismatch reports the wrong number.
    """
    text = normalize_ui_label(content_desc)
    if not text:
        return None
    if _matches(text, BUTTON_SELECTORS.action_label_like):
        return 'like'
    if _matches(text, BUTTON_SELECTORS.action_label_comment):
        return 'comment'
    if _matches(text, BUTTON_SELECTORS.action_label_share):
        return 'share'
    if _matches(text, BUTTON_SELECTORS.action_label_save):
        return 'save'
    return None


def is_like_button(content_desc: str) -> bool:
    """True when this action button is the LIKE one, in any supported language."""
    return classify_action_button(content_desc) == 'like'


def is_comment_button(content_desc: str) -> bool:
    """True when this action button is the COMMENT one, in any supported language."""
    return classify_action_button(content_desc) == 'comment'


def is_ui_label(text: str) -> bool:
    """True when ``text`` is a bare interface label rather than user content.

    Used by the username extractors: a row's action label ("Suivre", "Like") has the exact
    shape of a valid handle, so only the word tells them apart. EXACT match on the folded
    form — a substring test would reject the real account @likes.

    Both sides go through ``normalize_ui_label``: Instagram renders the TYPOGRAPHIC
    apostrophe in "J'aime" while catalogues are typed with the ASCII one, and comparing
    them raw never matched — the label passed for a username IN SILENCE.
    """
    folded = normalize_ui_label(text)
    if not folded:
        return False
    return any(folded == normalize_ui_label(lbl)
               for lbl in TEXT_READING_SELECTORS.not_a_username if lbl and lbl.strip())
