"""`_find_and_click(..., keep_out=...)` taps only the part of the target left clear, or nothing.

The screen is a real capture of TikTok 43.1.4 in French (Pixel 3a, anonymized): a video whose
follow button (`hi1`) is drawn over the bottom of the author's avatar (`yx4`), read by
uiautomator2's own `XPathEntry` through the shared device facade. When what must not be touched
covers the whole target (here the avatar's clickable wrapper `b4k`, [914,933][1080,1093]), the
answer is False and the phone receives no tap at all: a centre click, the fallback of an unguarded
tap, would land on what the caller said never to touch.
"""

import random

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.diagnostics import miss_capture
from unit.paths import CORE

VIDEO = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_video_follow_over_avatar.xml").read_text(
    encoding="utf-8"
)
AVATAR = ['//*[@resource-id="com.zhiliaoapp.musically:id/yx4"]']
FOLLOW = ['//*[@resource-id="com.zhiliaoapp.musically:id/hi1"]']
AVATAR_WRAPPER = ['//*[@resource-id="com.zhiliaoapp.musically:id/b4k"]']


class _Clock:
    """Time moves only when the code waits."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(0.0, seconds)


class _Phone:
    """Shows the capture, records every tap; the xpath queries are uiautomator2's."""

    wait_timeout = 0.0

    def __init__(self, screen):
        self.screen = screen
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.screen

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        self.taps.append((x, y))

    def long_click(self, x, y, _duration):
        self.taps.append((x, y))


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)


def test_a_covered_target_is_not_tapped_at_all():
    phone = _Phone(VIDEO)

    assert SharedBaseAction(phone)._find_and_click(AVATAR, timeout=1, keep_out=AVATAR_WRAPPER) is False

    assert phone.taps == []


def test_the_tap_lands_above_the_follow_button():
    for seed in range(50):
        phone = _Phone(VIDEO)
        random.seed(seed)

        assert SharedBaseAction(phone)._find_and_click(AVATAR, timeout=1, keep_out=FOLLOW) is True

        [(x, y)] = phone.taps
        # The avatar is [936,952][1057,1073]; the follow button starts at y 1027.
        assert 936 <= x < 1057 and 952 <= y < 1027, (seed, x, y)
