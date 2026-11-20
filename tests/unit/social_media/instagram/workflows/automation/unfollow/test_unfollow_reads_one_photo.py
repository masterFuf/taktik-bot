"""The unfollow and the profile visit read each screen on one photo (step 4 of the one-photo spec).

Each read below asked uiautomator2 one selector at a time, and each `d.xpath(...).exists` was a
dump: the check of a candidate's profile cost 7 dumps (the screen, then the handle selector by
selector), the wait for a confirmation dialog 10 in 2 s, the sort control 3, the tab guard one per
selector of each tab, and a profile visit read its flags and its texts on two dumps. Unchanged:
the answers, the order of the selectors, the timeouts and the pauses.

The phone is uiautomator2's own xpath engine behind the facade the Lab and every bridge mount
(`CloneAwareDeviceProxy`). The screens are real captures, anonymized: a verified business profile
and another profile (Instagram 410, English), the top of our own followers list (410, English).
"""

import time

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle, create_instagram_device_facade)
from taktik.core.social_media.instagram.services.profile.extraction import ProfileExtraction
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


VERIFIED_BUSINESS = _capture("ig410_en_profile_verified_business.xml")
OTHER_PROFILE = _capture("ig410_en_profile_following.xml")
OWN_FOLLOWERS = _capture("ig410_en_own_followers_newest_first_1.xml")


class _Phone:
    """One screen; its dumps counted, its gestures recorded."""

    wait_timeout = 1.0
    info = {"displayWidth": 1080, "displayHeight": 2400}
    settings = {"max_depth": 50}

    def __init__(self, screen):
        self.screen = screen
        self.dumps = 0
        self.gestures = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        return self.screen

    def click(self, x, y):
        self.gestures.append(("click", x, y))

    def long_click(self, x, y, _duration=None):
        self.gestures.append(("click", x, y))

    def press(self, key):
        self.gestures.append(("press", key))

    def window_size(self):
        return 1080, 2400

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "unknown"}


@pytest.fixture(autouse=True)
def _english_and_still_clock(monkeypatch):
    set_active_locale("en")
    now = [100.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    yield
    set_active_locale(None)


def _bundle(screen):
    phone = _Phone(screen)
    return build_instagram_action_bundle(create_instagram_device_facade(phone)), phone


def _dumps_of(phone, read):
    before = phone.dumps
    answer = read()
    return answer, phone.dumps - before


def test_the_candidate_profile_is_recognised_on_one_photo():
    bundle, phone = _bundle(OTHER_PROFILE)

    assert _dumps_of(phone, lambda: bundle.unfollow._on_profile_of("user_1")) == (True, 1)
    assert _dumps_of(phone, lambda: bundle.unfollow._on_profile_of("someone_else")) == (False, 1)


def test_the_handle_of_a_profile_is_one_dump():
    bundle, phone = _bundle(OTHER_PROFILE)

    assert _dumps_of(phone, bundle.detection.get_username_from_profile) == ("user_1", 1)


def test_no_confirmation_dialog_is_one_dump_a_turn():
    bundle, phone = _bundle(OTHER_PROFILE)

    # A photo at 0, 0.3, ... 2.1 s, the deadline passed at the last: 8 photos for all the
    # selectors, where each selector took its own dump each turn.
    answer, dumps = _dumps_of(phone, lambda: bundle.unfollow._tap_unfollow_confirm(timeout=2.0))

    assert answer is False and phone.gestures == []
    assert dumps == 8


def test_the_list_guards_read_one_photo():
    bundle, phone = _bundle(OWN_FOLLOWERS)
    unfollow = bundle.unfollow

    assert _dumps_of(phone, unfollow._list_shows_sort_control)[1] == 1
    assert _dumps_of(phone, lambda: unfollow._list_tab_count("followers"))[1] == 1
    # Our followers tab is the one shown: the guard reads the layout and the tab on one photo.
    assert _dumps_of(phone, unfollow._ensure_followers_tab) == (True, 1)


def test_the_visit_reads_its_flags_and_texts_on_one_photo():
    bundle, phone = _bundle(VERIFIED_BUSINESS)
    extraction = ProfileExtraction(bundle.device)
    # What this test does not measure: the header counters, the button, the avatar.
    extraction._get_followers_count_robust = lambda: 1
    extraction._get_following_count_robust = lambda: 1
    extraction._get_posts_count_robust = lambda: 1
    extraction.click_actions.get_follow_button_state = lambda: "follow"
    extraction.detection_actions.extract_profile_image = lambda: None

    info, dumps = _dumps_of(phone, lambda: extraction.get_complete_profile_info(
        username="name_10", navigate_if_needed=False, emit_ipc=False, save_to_db=False))

    assert (info["is_verified"], info["is_business"], info["is_private"]) == (True, True, False)
    assert info["username"] == "name_10"
    assert dumps == 1
