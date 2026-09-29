"""Reading which login screen is up taps nothing; only the login flow picks a saved profile.

Found by the Lab auto-test on 2026-09-28: `account.detect_login_screen`, a detection, ran
`InstagramLogin._is_on_login_screen`, which on the saved-profiles screen TAPS a profile tile or
"Use another profile" before it answers, and so did the login's result check. Reading and acting
were one function. On a real login form it went wrong too: "Create new account", a button of the
login form as much as of the saved-profiles screen, made it take the form for that screen, and with
the account's name already in the username field it tapped the field as a "saved profile tile" and
answered "tile tapped, wait for the home feed".

Now `_read_login_screen` only reads (the form, the saved-profiles screen, or neither), and
`_reach_login_form` is the login step that may tap, called by the login flow alone.

The screens are real captures, anonymized: Instagram's login form in English with a username typed
(version not recorded, May 2026), and the home feed of Instagram 410 in English (Pixel 3a).
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.tools.lab.actions.instagram import register_actions
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.actions.account.login import InstagramLogin
from taktik.core.social_media.instagram.ui.selectors import locales

FIXTURES = Path(__file__).parent / "fixtures"
LOGIN_FORM = (FIXTURES / "ig_en_login_form_username_filled.xml").read_text(encoding="utf-8")
HOME_FEED = (FIXTURES / "ig410_en_home_feed_carousel_post.xml").read_text(encoding="utf-8")


class _Phone:
    """uiautomator2 as the facade touches it: `xpath()`, one dump, and the taps it would inject."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "demo.Activity"}

    def click(self, x, y):
        self.taps.append((x, y))


@pytest.fixture(autouse=True)
def english():
    before = locales.active_locale()
    locales.set_active_locale("en")
    register_actions()
    yield
    locales.set_active_locale(before)


def _login(xml):
    phone = _Phone(xml)
    return InstagramLogin(create_instagram_device_facade(phone), "serial"), phone


def test_the_login_form_is_read_as_the_login_form_and_nothing_is_tapped():
    login, phone = _login(LOGIN_FORM)
    assert login._read_login_screen() == "login_form"
    assert phone.taps == []


def test_the_home_feed_is_neither_login_screen():
    login, phone = _login(HOME_FEED)
    assert login._read_login_screen() is None
    assert phone.taps == []


def test_the_login_step_on_the_form_with_the_name_typed_taps_no_tile():
    """The username in the field is not a saved profile tile: the form is reached, nothing tapped."""
    login, phone = _login(LOGIN_FORM)
    assert login._reach_login_form(target_username="user_1") is True
    assert phone.taps == []


def test_the_login_result_check_on_the_form_taps_nothing():
    login, phone = _login(LOGIN_FORM)
    result = login._detect_login_result()
    assert (result.success, result.error_type) == (False, "unknown")  # "Still on login screen"
    assert phone.taps == []


@pytest.mark.parametrize("xml, found", [(LOGIN_FORM, True), (HOME_FEED, False)], ids=["login-form", "home-feed"])
def test_the_lab_detection_answers_and_taps_nothing(xml, found):
    phone = _Phone(xml)
    bundle = build_instagram_action_bundle(create_instagram_device_facade(phone))
    result = INSTAGRAM_ACTIONS["account.detect_login_screen"](bundle, {})
    assert (result["success"], result["details"]) == (True, {"found": found})
    assert phone.taps == []
