"""The sound harvest opens a video's author through the avatar, never through « Suivre ».

`SoundActions.collect_sound_users` opens each video of a sound page and taps the author's avatar to
reach the profile. On TikTok 43.1.4 the follow button (`hi1`, [914,1027][1080,1122]) is drawn over
the bottom of that avatar (`yx4`, [936,952][1057,1073]; drawing order 3 over 2): a humanized tap
sampled over the whole avatar lands in their common band about one time in four, and the account
follows the author. Four Lab passes in a row on the Pixel 3a followed one author each
(`tt.sound.collect_users`, 29 and 30/09).

The screen is a real dump of TikTok 43.1.4 in French (Pixel 3a): the video whose sound page the
harvest opened on 30/09, anonymized (`scripts/lab/anonymize_dump.py`), read by uiautomator2's own
`XPathEntry` through the production action and the device facade. Every seed of the tap jitter is
played; the tap must land on the avatar, and outside the follow button, every time.
"""

import random

import pytest
import uiautomator2.xpath as u2_xpath
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
import taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions as sound_module
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions
from taktik.core.social_media.tiktok.actions.base.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.creator import VIDEO_CREATOR_SELECTORS
from unit.paths import CORE

VIDEO = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_video_follow_over_avatar.xml").read_text(
    encoding="utf-8"
)

#: The seeds of the tap jitter played. Before the fix about one tap in four followed the author, so
#: two hundred seeds leave no chance of a green run on the broken code.
SEEDS = range(200)


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
def _french_phone_no_waits(monkeypatch):
    clock = _Clock()
    for module in (u2_xpath, shared_base_action, shared_facade, sound_module):
        monkeypatch.setattr(module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)


def _bounds_of(selectors):
    found = first_matching(_Phone(VIDEO), selectors)
    assert found, selectors
    return found[0].bounds


def _inside(point, bounds):
    """Android's hit test: the left and top edges belong to the element, the right and bottom do not."""
    x, y = point
    left, top, right, bottom = bounds
    return left <= x < right and top <= y < bottom


def test_the_capture_shows_the_follow_button_over_the_avatar():
    avatar = _bounds_of(VIDEO_CREATOR_SELECTORS.author_username)
    follow = _bounds_of(VIDEO_CREATOR_SELECTORS.follow_button)

    assert avatar == (936, 952, 1057, 1073)
    assert follow == (914, 1027, 1080, 1122)
    # The follow button spans the avatar's whole width and covers the bottom of it.
    assert follow[0] <= avatar[0] and follow[2] >= avatar[2]
    assert avatar[1] < follow[1] < avatar[3]


def test_no_seed_of_the_jitter_taps_the_follow_button():
    avatar = _bounds_of(VIDEO_CREATOR_SELECTORS.author_username)
    follow = _bounds_of(VIDEO_CREATOR_SELECTORS.follow_button)

    on_follow = []
    for seed in SEEDS:
        phone = _Phone(VIDEO)
        random.seed(seed)

        assert SoundActions(phone)._open_video_author() is True

        assert len(phone.taps) == 1, (seed, phone.taps)
        tap = phone.taps[0]
        assert _inside(tap, avatar), (seed, tap)
        if _inside(tap, follow):
            on_follow.append((seed, tap))

    assert on_follow == []
