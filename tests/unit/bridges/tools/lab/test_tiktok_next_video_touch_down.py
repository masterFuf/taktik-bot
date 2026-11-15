"""`tt.scroll.next_video` says where the finger of the feed advance went down, and why there.

The Lab runs the production advance (`ScrollActions.scroll_to_next_video`), whose touch-down the
shared engine keeps off the buttons of the video. The action hands back that touch-down and its
source, as the Instagram probe `scroll.feed_drag` does: a run of advances on a phone proves that
none lands on a button. The screens are real captures, anonymized: a For You video of 43.1.4, then
a video of 46.9.3 as the next one.
"""

import time

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.actions.tiktok import ACTION_REGISTRY, register_actions
from bridges.tools.lab.action_test.bundles.tiktok import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
VIDEO = (FIXTURES / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")
NEXT_VIDEO = (FIXTURES / "tt4693_fr_search_result_video.xml").read_text(encoding="utf-8")
#: The like button of the first capture (left, top, right, bottom).
LIKE = (912, 1414, 1080, 1572)


class _Phone:
    """The video, then the next one once a swipe is made."""

    wait_timeout = 0.2
    info = {"displayWidth": 1080, "displayHeight": 2400}

    def __init__(self):
        self.screens = [VIDEO, NEXT_VIDEO]
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.screens[0]

    def app_current(self):
        return {"package": "com.zhiliaoapp.musically", "activity": "demo.Activity"}

    def window_size(self):
        return 1080, 2400

    def swipe(self, *_a, **_k):
        self.screens = self.screens[1:] or self.screens

    swipe_points = swipe


@pytest.fixture(autouse=True)
def french(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def test_the_advance_reports_its_touch_down_and_its_source():
    register_actions()
    bundle = build_tiktok_action_bundle(create_tiktok_device_facade(_Phone()))
    result = ACTION_REGISTRY["tt.scroll.next_video"](bundle, {})
    assert result["success"] is True
    start = result["details"]["gesture_start"]
    assert start["source"] in ("ui_bounds", "ui_bounds_clear")
    x, y = start["final"]
    left, top, right, bottom = LIKE
    assert not (left <= x <= right and top <= y <= bottom)
