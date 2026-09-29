"""An empty comments thread is closed again, checked: its composer takes the focus, one Back is not enough.

Measured on a Pixel 3a (Instagram 410, in English), Lab auto-test, 2026-09-28: `post.open_comments` on a
suggested post of the home feed tapped the comment button, found "No comments yet", pressed Back once
and answered "not opened". The sheet was still up: the empty thread gives its composer the focus and
the keyboard, and that Back only hid the keyboard. The five tests after it ran on the sheet (the
comment button no longer on screen), and so would every step of a run after an empty thread.

The screens are real dumps, anonymized: the feed with that post (its action row on screen), and the
empty thread as the phone showed it after the one Back (sheet up, composer focused, no keyboard). The
phone answers `xpath` from the screen on show; a tap on the comment button opens the thread; on the
thread the first Back hides the keyboard, the next one closes the sheet.
"""

from pathlib import Path

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from bridges.tools.lab.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.tools.lab.actions.instagram import register_actions as register_instagram
from bridges.tools.lab.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

PKG = "com.instagram.android"
FIXTURES = Path(__file__).parent / "fixtures"
SCREENS = {
    "feed": (FIXTURES / "ig410_en_feed_suggested_post_no_comment.xml").read_text(encoding="utf-8"),
    "empty thread": (FIXTURES / "ig410_en_comment_sheet_empty_composer_focused.xml").read_text(encoding="utf-8"),
}


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def _comment_button_areas():
    """The comment button of the feed's post, and the clickable parent that owns its touch target."""
    root = etree.fromstring(SCREENS["feed"].encode("utf-8"))
    (button,) = root.xpath(f'//*[@resource-id="{PKG}:id/row_feed_button_comment"]')
    return [_bounds(button), _bounds(button.getparent())]


class _Phone:
    wait_timeout = 0.0

    def __init__(self):
        self.screen = "feed"
        self.keyboard_up = False
        self.backs = 0
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG, "activity": "com.instagram.mainactivity.InstagramMainActivity"}

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        if self.screen == "feed" and any(l <= x <= r and t <= y <= b for l, t, r, b in _comment_button_areas()):
            self.screen = "empty thread"
            self.keyboard_up = True

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key, *_a):
        if key != "back":
            return False
        self.backs += 1
        if self.screen == "empty thread":
            if self.keyboard_up:
                self.keyboard_up = False
            else:
                self.screen = "feed"
        return True


@pytest.fixture(autouse=True)
def _quick(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    register_instagram()
    set_active_locale("en")
    yield
    set_active_locale(None)


def _bundle(phone):
    return build_instagram_action_bundle(create_instagram_device_facade(phone))


def test_an_empty_thread_is_reported_not_opened_and_left_closed():
    phone = _Phone()
    assert _bundle(phone).popup._open_comments_view() is False
    assert phone.screen == "feed"
    assert phone.backs == 2


def test_the_lab_declares_the_empty_thread_not_applicable():
    phone = _Phone()
    result = INSTAGRAM_ACTIONS["post.open_comments"](_bundle(phone), {})
    assert result["success"] is False
    assert result["details"]["not_applicable"] == "the post on screen has no comment yet (its empty thread closed again)"
    assert phone.screen == "feed"
