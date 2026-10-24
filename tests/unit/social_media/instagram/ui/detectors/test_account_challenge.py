"""Instagram checking the account is seen, said, and never touched.

On 2026-10-24 Instagram opened its account check on a running account (410, Pixel 6 Pro, Android
17): « Confirmez que vous êtes une personne réelle afin d'utiliser votre compte », a « Continuer »
button, the page in `bloks_container`, activity `com.instagram.challenge.activity.ChallengeActivity`.
Nothing knew that screen: the run looked for its tab bar three times fifteen seconds, pressed Back
between the tries, and ended `navigation_lost`, as if it had only lost its way.

The screen is the real capture, anonymized (`ig410_fr_account_challenge.xml`); the activity is
what the Lab read on that phone at that moment. The English check was never captured: in English
only the activity proves it, and no English headline is invented.
"""

from pathlib import Path

import pytest

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation import TabNavigationMixin
from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.workflows.common.session import stop_reasons
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
CHALLENGE = (FIXTURES / "ig410_fr_account_challenge.xml").read_text(encoding="utf-8")
OWN_PROFILE = (FIXTURES / "ig410_fr_own_profile.xml").read_text(encoding="utf-8")
CHALLENGE_ACTIVITY = "com.instagram.challenge.activity.ChallengeActivity"


class _Phone:
    """Shows one screen, answers `app_current` (or cannot), and records every gesture."""

    def __init__(self, screen, activity=CHALLENGE_ACTIVITY):
        self.screen = screen
        self.activity = activity
        self.gestures = []
        self.activity_reads = 0

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        self.activity_reads += 1
        if self.activity is None:
            raise RuntimeError("dumpsys unavailable")
        return {"package": "com.instagram.android", "activity": self.activity}

    def press(self, key):
        self.gestures.append(f"press {key}")

    def click(self, *_a, **_k):
        self.gestures.append("click")

    def swipe(self, *_a, **_k):
        self.gestures.append("swipe")

    def xpath(self, *_a, **_k):
        raise AssertionError("nothing is looked up on the account check, so nothing can be tapped")

    def __call__(self, **_selector):
        raise AssertionError("nothing is looked up on the account check, so nothing can be tapped")


@pytest.fixture(autouse=True)
def fresh_latch():
    run_halt.reinitialiser()
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)
    run_halt.reinitialiser()


def _halt_code():
    return (run_halt.arret_demande() or {}).get("code")


def test_the_check_stops_the_run_after_a_gesture_and_nothing_is_touched():
    phone = _Phone(CHALLENGE)

    assert ProblematicPageDetector(phone).is_action_blocked() is True
    assert _halt_code() == "account_challenge"
    assert (run_halt.arret_demande() or {}).get("evidence") == "activity"
    assert phone.gestures == []


def test_the_check_of_pages_names_it_and_leaves_it_open():
    phone = _Phone(CHALLENGE)

    result = ProblematicPageDetector(phone).detect_and_handle_problematic_pages()

    assert result == {"detected": True, "closed": False, "soft_ban": True, "page_type": "account_challenge"}
    assert _halt_code() == "account_challenge"
    assert phone.gestures == []


def test_without_the_activity_the_french_headline_proves_it():
    phone = _Phone(CHALLENGE, activity=None)

    assert ProblematicPageDetector(phone).is_account_challenged() is True
    assert (run_halt.arret_demande() or {}).get("evidence") == "words"


def test_in_english_only_the_activity_proves_it():
    locales.set_active_locale("en")

    assert ProblematicPageDetector(_Phone(CHALLENGE)).is_account_challenged() is True
    run_halt.reinitialiser()
    # No English headline was ever read on a phone: without the activity, nothing proves it.
    assert ProblematicPageDetector(_Phone(CHALLENGE, activity=None)).is_account_challenged() is False
    assert run_halt.arret_demande() is None


def test_the_own_profile_is_not_the_check_and_costs_no_activity_read():
    phone = _Phone(OWN_PROFILE)

    assert ProblematicPageDetector(phone).is_account_challenged() is False
    assert phone.activity_reads == 0
    assert run_halt.arret_demande() is None


def test_another_activity_on_a_bloks_page_is_not_the_check():
    locales.set_active_locale("en")
    phone = _Phone(CHALLENGE, activity="com.instagram.mainactivity.InstagramMainActivity")

    assert ProblematicPageDetector(phone).is_account_challenged() is False
    assert run_halt.arret_demande() is None


def test_a_navigation_without_its_tab_bar_presses_no_back_on_the_check():
    phone = _Phone(CHALLENGE)
    backs = []
    navigation = TabNavigationMixin.__new__(TabNavigationMixin)
    navigation.problematic_page_detector = ProblematicPageDetector(phone)
    navigation._back_one_screen = lambda: backs.append("back")

    assert navigation._back_out_until(lambda: False) is False
    assert backs == []
    assert _halt_code() == "account_challenge"


def test_the_run_ends_on_the_check_not_on_the_lost_navigation():
    halt = {"code": "account_challenge"}

    settled = stop_reasons.settled_by_halt(stop_reasons.navigation_lost(), halt)

    assert settled.code == "account_challenge"
    assert stop_reasons.terminal_status(settled) == stop_reasons.STATUS_INTERRUPTED
    assert stop_reasons.for_halt(halt).code == "account_challenge"
    # A manual stop, a crash and an expected end keep their own motive.
    for reason in (stop_reasons.manual_stop(), stop_reasons.crashed("boom"), stop_reasons.duration_cap(30)):
        assert stop_reasons.settled_by_halt(reason, halt) is reason
