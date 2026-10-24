"""The likers of a post are read in their popup only: without it, nothing is read and nothing is scrolled.

Measured on a Pixel 6 Pro (Instagram 410, Android 17, in French, 2026-10-24), Lab action
`post.read_likers` on a profile's posts with no popup open (`popups.is_likers_open` = no): ten drags
"in the likers popup" went down the post list under it, for "0 liker(s)". The reading
(`LikerExtractionMixin._extract_likers_after_click`, the one of the runs and of the Lab) scrolled
whatever was on screen.

The screen is a real dump, anonymized: `ig410_fr_profile_posts_framed_row_below_6pro.xml`, the posts of
a public profile on that phone, the screen of that run. The host is the Lab's `a.popup`,
`BaseBusinessAction`, built by its own constructor on a phone that replays the capture and records
every gesture injected into it.
"""

import time

import pytest

from profile_posts_phone import PKG, ProfilePostsPhone, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.base.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

NO_POPUP_6PRO = "ig410_fr_profile_posts_framed_row_below_6pro.xml"
PIXEL_6_PRO_H = 3120


class _GesturePhone(ProfilePostsPhone):
    """The replayed phone, which also records what a drag or a swipe injects."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.gestures = []

    def swipe_points(self, points, duration):
        self.gestures.append(("swipe_points", [tuple(p) for p in points]))

    def swipe(self, *args, **kwargs):
        self.gestures.append(("swipe", args))

    def drag(self, *args, **kwargs):
        self.gestures.append(("drag", args))


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    # Every wait of the reading, the 2 s it gave the usernames and the pauses between its scrolls.
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _lab_popup_host(phone):
    host = BaseBusinessAction(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    host._human_like_delay = lambda *_args, **_kwargs: None
    return host


def test_the_captured_screen_has_no_likers_popup():
    phone = _GesturePhone(screen=capture(NO_POPUP_6PRO), height=PIXEL_6_PRO_H)

    assert _lab_popup_host(phone)._is_likers_popup_open() is False


def test_no_popup_no_reading_and_no_gesture():
    phone = _GesturePhone(screen=capture(NO_POPUP_6PRO), height=PIXEL_6_PRO_H)

    likers = _lab_popup_host(phone)._extract_likers_after_click(max_interactions=10, multiply_by=1)

    assert likers == []
    assert phone.gestures == [], f"{len(phone.gestures)} gesture(s) on a screen without the likers popup"
    assert phone.taps == []
