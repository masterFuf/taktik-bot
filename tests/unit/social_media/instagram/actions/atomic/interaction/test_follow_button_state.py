"""Anti-regression: the profile-header button must reveal the REAL relationship.

Background (2026-07-18): a Target run re-interacted with profiles that already followed the
operated account. Root cause: `get_follow_button_state()` matched the button text against
hardcoded stems in this order -> ('following', 'abonné', 'suivi') then ('follow', 'suivre').
A "Suivre en retour" button contains "suivre" but NOT "suivi", so it fell through to the
'follow' branch and an existing follower was read as a brand-new target. Same in English:
"Follow back" contains "follow". The 'follow_back' state simply did not exist.

The screens are real profiles of Instagram 410.0.0.53.71, anonymized: in French (Pixel 3) a
"Suivre en retour" profile, a "Suivi(e)" profile and a "Suivre" profile, the last two with the
`profile_header_follow_context_text` decoy ("Suivi(e) par X, Y" = mutual friends), a
NON-clickable TextView sitting just above the button — a bare text match hits it instead of the
button; in English (Pixel 3) a "Follow" profile under its "Followed by" line, and (Pixel 3a,
2026-09-27) a "Follow back" profile and a "Following" profile under its "Followed by" line. They
are read the way `d.xpath()` reads them (`parse_ui_dump`).
"""

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import (
    ProfileInteractionMixin,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
CONTEXT_ID = "com.instagram.android:id/profile_header_follow_context_text"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


FR_FOLLOW_BACK = _screen("ig410_fr_profile_follow_back.xml")
FR_FOLLOWING = _screen("ig410_fr_profile_following.xml")
FR_FOLLOW = _screen("ig410_fr_profile_follow_with_mutuals.xml")
EN_FOLLOW = _screen("ig410_en_profile_follow_with_mutuals.xml")
EN_FOLLOW_BACK = _screen("ig410_en_profile_follow_back.xml")
EN_FOLLOWING = _screen("ig410_en_profile_following.xml")


class _XPathResult:
    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def exists(self) -> bool:
        return len(self._nodes) > 0

    def get_text(self):
        if not self._nodes:
            return None
        return self._nodes[0].get("text")


class _XmlDevice:
    def __init__(self, xml: str):
        self._tree = parse_ui_dump(xml)

    def xpath(self, selector: str) -> _XPathResult:
        return _XPathResult(self._tree.xpath(selector))


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None


class _Reader(ProfileInteractionMixin):
    """Minimal host: the state read only needs `device` + the selectors property."""

    def __init__(self, xml: str):
        self.device = _XmlDevice(xml)
        self.logger = _NoopLogger()

    @property
    def profile_selectors(self):
        return PROFILE_SELECTORS

    def _is_element_present(self, _selectors) -> bool:
        # The Message-button fallback is out of scope here; force the button read to decide.
        return False


def _context_line(xml: str) -> str:
    return parse_ui_dump(xml).xpath(f'//*[@resource-id="{CONTEXT_ID}"]')[0].get("text")


# ── The bug: a profile that already follows US ────────────────────────────────────

def test_fr_follow_back_is_not_read_as_a_fresh_target():
    set_active_locale("fr")
    reader = _Reader(FR_FOLLOW_BACK)
    assert reader.get_follow_button_state() == "follow_back"


def test_en_follow_back_is_not_read_as_a_fresh_target():
    set_active_locale("en")
    reader = _Reader(EN_FOLLOW_BACK)
    assert reader.get_follow_button_state() == "follow_back"


# ── We already follow THEM ────────────────────────────────────────────────────────

def test_fr_following():
    set_active_locale("fr")
    assert _Reader(FR_FOLLOWING).get_follow_button_state() == "following"


def test_en_following():
    set_active_locale("en")
    assert _Reader(EN_FOLLOWING).get_follow_button_state() == "following"


# ── No relationship: the normal target ────────────────────────────────────────────

def test_fr_plain_follow():
    set_active_locale("fr")
    assert _Reader(FR_FOLLOW).get_follow_button_state() == "follow"


def test_en_plain_follow():
    set_active_locale("en")
    assert _Reader(EN_FOLLOW).get_follow_button_state() == "follow"


# ── The mutual-friends decoy must never drive the verdict ─────────────────────────

def test_mutual_friends_label_does_not_flip_a_fresh_target():
    """"Suivi(e) par X, Y" sits above a plain "Suivre" button: the state stays 'follow'."""
    set_active_locale("fr")
    assert _context_line(FR_FOLLOW).startswith("Suivi(e) ")
    assert _Reader(FR_FOLLOW).get_follow_button_state() == "follow"


def test_mutual_friends_label_does_not_mask_the_english_follow():
    set_active_locale("en")
    assert _context_line(EN_FOLLOW).startswith("Followed by ")
    assert _Reader(EN_FOLLOW).get_follow_button_state() == "follow"


def test_mutual_friends_label_does_not_mask_following():
    set_active_locale("fr")
    assert _context_line(FR_FOLLOWING).startswith("Suivi(e) ")
    assert _Reader(FR_FOLLOWING).get_follow_button_state() == "following"


def test_mutual_friends_label_does_not_mask_the_english_following():
    set_active_locale("en")
    assert _context_line(EN_FOLLOWING).startswith("Followed by ")
    assert _Reader(EN_FOLLOWING).get_follow_button_state() == "following"


# ── Locale-agnostic safety net ────────────────────────────────────────────────────

@pytest.mark.parametrize("xml, state", [
    (FR_FOLLOW_BACK, "follow_back"),
    (EN_FOLLOW_BACK, "follow_back"),
    (FR_FOLLOWING, "following"),
    (EN_FOLLOWING, "following"),
    (FR_FOLLOW, "follow"),
    (EN_FOLLOW, "follow"),
], ids=["fr_follow_back", "en_follow_back", "fr_following", "en_following", "fr_follow",
        "en_follow"])
def test_states_hold_without_language_detection(xml, state):
    """If detect_and_optimize never ran, L() falls back to the multi-language union.

    The state labels are disjoint across languages, so the ordered detection still holds — a
    Lab run (or any path missing the locale setup) must not report a different state.
    """
    set_active_locale(None)
    assert _Reader(xml).get_follow_button_state() == state
