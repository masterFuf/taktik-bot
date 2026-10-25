"""The Lab plays the check of pages the navigation makes, and says what it saw and did.

`popups.check_problematic_pages` calls the production check (`detect_and_handle_problematic_pages`)
on the navigation's own detector, built by the Lab's bundle as the production navigation builds it.
It reports the page detected, whether it was closed or left open, and a screen it could not read
(never "nothing detected"); "nothing detected" counts only on a screen of Instagram's.

The screens are real dumps, anonymized: the home feed and the options sheet of another profile over
that profile (Instagram 410, English), Instagram checking the account (410, French), and a For You
video of TikTok (43.1.4), another app in front.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY, register_actions
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.ui.detectors import problematic_page
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

INSTAGRAM = CORE / "tests/unit/social_media/instagram/fixtures"
FEED = (INSTAGRAM / "ig410_en_home_feed_carousel_post.xml").read_text(encoding="utf-8")
OPTIONS_SHEET = (INSTAGRAM / "ig410_en_profile_options_sheet.xml").read_text(encoding="utf-8")
PROFILE = (INSTAGRAM / "ig410_en_profile_following.xml").read_text(encoding="utf-8")
CHALLENGE = (INSTAGRAM / "ig410_fr_account_challenge.xml").read_text(encoding="utf-8")
TIKTOK_VIDEO = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")

ACTION = "popups.check_problematic_pages"


class _Phone:
    """uiautomator2 as the Lab's bundle touches it; a gesture shows the screen behind."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2160}

    def __init__(self, screen, behind=None, package="com.instagram.android",
                 activity="com.instagram.mainactivity.MainActivity"):
        self.screen, self.behind = screen, behind
        self.package, self.activity = package, activity
        self.gestures = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def app_current(self):
        return {"package": self.package, "activity": self.activity}

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
def _setup(monkeypatch):
    monkeypatch.setattr(problematic_page.time, "sleep", lambda *_a, **_k: None)
    register_actions()
    set_active_locale("en")
    run_halt.reinitialiser()
    yield
    set_active_locale(None)
    run_halt.reinitialiser()


def _check(phone):
    return ACTION_REGISTRY[ACTION](build_instagram_action_bundle(create_instagram_device_facade(phone)), {})


def test_nothing_on_the_feed_is_said_and_nothing_is_touched():
    phone = _Phone(FEED)

    result = _check(phone)

    assert result["success"] is True
    assert result["message"] == "no problematic page"
    assert result["details"] == {"unreadable": False, "detected": False, "closed": False,
                                 "pageType": None, "softBan": False}
    assert phone.gestures == []


def test_the_options_sheet_is_closed_by_one_tap_above_it():
    phone = _Phone(OPTIONS_SHEET, behind=PROFILE)

    result = _check(phone)

    assert result["success"] is True
    assert result["details"] == {"unreadable": False, "detected": True, "closed": True,
                                 "pageType": "follow_options_bottom_sheet", "softBan": False}
    assert len(phone.gestures) == 1 and phone.gestures[0][0] == "click"
    assert phone.gestures[0][2] < 609  # above the sheet's grab bar on the capture


def test_the_account_check_is_left_open_and_said():
    set_active_locale("fr")
    phone = _Phone(CHALLENGE, activity="com.instagram.challenge.activity.ChallengeActivity")

    result = _check(phone)

    assert result["success"] is True
    assert result["message"] == "account_challenge: left open (the run would stop)"
    assert result["details"]["closed"] is False and result["details"]["softBan"] is True
    assert phone.gestures == []


def test_a_screen_that_cannot_be_read_is_no_answer():
    result = _check(_Phone(""))

    assert result["success"] is False
    assert result["details"]["unreadable"] is True
    assert result["details"]["detected"] is None


def test_another_app_in_front_is_no_answer_never_nothing_detected():
    phone = _Phone(TIKTOK_VIDEO, package="com.zhiliaoapp.musically")

    result = _check(phone)

    assert result["success"] is False
    assert result["details"]["detected"] is None
    assert phone.gestures == []
