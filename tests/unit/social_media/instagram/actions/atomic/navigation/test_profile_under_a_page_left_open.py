"""A profile opened under a page that was not closed is not an opened profile.

After every opening of a profile, the navigation checks the pages
(`_check_and_close_problematic_pages`). A page detected and left open (Instagram checking the
account, an alert with no cancel button, a close that failed) was logged and forgotten:
`navigate_to_profile` answered True, and the workflow went on to read and act on a profile hidden
under that page. The check now says whether the screen is clear, and the navigation answers it,
without trying its other route over the page.

The screens are real dumps, anonymized: Instagram checking the account (410, French), the options
sheet of another profile over that profile (410, English), and that profile.
"""

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.navigation import search_navigation
from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.selectors import locales
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
CHALLENGE = (FIXTURES / "ig410_fr_account_challenge.xml").read_text(encoding="utf-8")
OPTIONS_SHEET = (FIXTURES / "ig410_en_profile_options_sheet.xml").read_text(encoding="utf-8")
PROFILE = (FIXTURES / "ig410_en_profile_following.xml").read_text(encoding="utf-8")
CHALLENGE_ACTIVITY = "com.instagram.challenge.activity.ChallengeActivity"
MAIN_ACTIVITY = "com.instagram.mainactivity.MainActivity"


class _Phone:
    """uiautomator2 as the navigation's detector reads it; a gesture shows the screen behind."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen, behind=None, activity=MAIN_ACTIVITY):
        self.screen, self.behind, self.activity = screen, behind, activity
        self.gestures = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        if isinstance(self.screen, Exception):
            raise self.screen
        return self.screen

    def app_current(self):
        return {"package": "com.instagram.android", "activity": self.activity}

    def window_size(self):
        return 1080, 2160

    def _gesture(self, gesture):
        self.gestures.append(gesture)
        if self.behind is not None:
            self.screen = self.behind

    def click(self, x, y):
        self._gesture(("click", x, y))

    def press(self, key):
        self._gesture(("press", key))

    def swipe(self, *_a, **_k):
        self._gesture(("swipe",))


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(search_navigation, "get_active_package", lambda: "com.instagram.android")
    run_halt.reinitialiser()
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)
    run_halt.reinitialiser()


@pytest.fixture
def warnings_logged():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


def _navigation(phone, routes):
    """The production navigation; its two routes to a profile stubbed, recorded in `routes`."""
    navigation = NavigationActions(phone)
    navigation._navigate_via_search = lambda username: routes.append("search") or True
    navigation._navigate_via_deep_link = lambda username: routes.append("deep link") or True
    return navigation


def test_a_profile_under_the_account_check_is_not_opened():
    phone = _Phone(CHALLENGE, activity=CHALLENGE_ACTIVITY)
    routes = []

    assert _navigation(phone, routes).navigate_to_profile("demo_user") is False
    assert routes == ["search"]  # no second route over the page
    assert phone.gestures == []
    assert (run_halt.arret_demande() or {}).get("code") == "account_challenge"


def test_a_sheet_closed_after_the_navigation_leaves_the_profile_opened():
    locales.set_active_locale("en")
    phone = _Phone(OPTIONS_SHEET, behind=PROFILE)
    routes = []

    assert _navigation(phone, routes).navigate_to_profile("demo_user") is True
    assert routes == ["search"]
    assert len(phone.gestures) == 1


def test_a_clear_profile_is_opened():
    locales.set_active_locale("en")
    phone = _Phone(PROFILE)

    assert _navigation(phone, []).navigate_to_profile("demo_user") is True
    assert phone.gestures == []


def test_the_check_of_pages_says_whether_the_screen_is_clear(warnings_logged):
    navigation = NavigationActions(_Phone(CHALLENGE, activity=CHALLENGE_ACTIVITY))

    assert navigation._check_and_close_problematic_pages() is False
    assert any("left open" in line for line in warnings_logged)


def test_an_unread_screen_after_the_navigation_is_said(warnings_logged):
    navigation = NavigationActions(_Phone(RuntimeError("uiautomator2 server gone")))

    # Nothing is proven on screen: the navigation stands, the log says the pages were not checked.
    assert navigation._check_and_close_problematic_pages() is True
    assert any("screen unreadable" in line for line in warnings_logged)
