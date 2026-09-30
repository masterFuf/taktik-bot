"""Opening the DM inbox answers by arrival: a visited profile's Message button is not the inbox.

Measured on a Pixel 3a (Instagram 410, in English), Lab auto-test: `dm.open_inbox`, played on the
profile of a public account, found no Direct tab, tapped the first element described "Message" -- the
profile's Message button -- and answered "DM inbox open" on an empty conversation with that account.
The next test typed into that screen (the composer had no focus: nothing landed). The production
opener (`navigate_to_dm_inbox`) returned True on every tap without looking where it had landed.

The screens are real dumps, anonymized: the home feed and a visited profile with its Message button
(existing fixtures), the DM inbox and the empty conversation the tap opened (the auto-test's own
captures). The phone answers `d(...)` and `xpath` from the screen on show; a tap on the Direct tab
opens the inbox, a tap on the Message button opens the conversation, Back returns.
"""

import re

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.instagram.workflows.dm.navigation as navigation
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.workflows.dm.navigation import DMInboxNavigationMixin
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREENS = {
    "home": (FIXTURES / "ig410_en_home_feed_carousel_post.xml").read_text(encoding="utf-8"),
    "profile": (FIXTURES / "ig410_en_profile_with_message_button.xml").read_text(encoding="utf-8"),
    "inbox": (FIXTURES / "ig410_en_dm_inbox.xml").read_text(encoding="utf-8"),
    "conversation": (FIXTURES / "ig410_en_dm_thread_new_conversation.xml").read_text(encoding="utf-8"),
}
#: What a tap opens: (screen, bounds of the element) -> the screen it brings up.
DOORS = {
    ("home", (432, 1967, 648, 2088)): "inbox",  # the Direct tab
    ("profile", (496, 877, 943, 965)): "conversation",  # the profile's Message button
}


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


_UI_SELECTOR = {
    "text": lambda node, value: node.get("text") == value,
    "description": lambda node, value: node.get("content-desc") == value,
    "descriptionContains": lambda node, value: value in (node.get("content-desc") or ""),
    "resourceId": lambda node, value: node.get("resource-id") == value,
    # uiautomator's regex: the whole id must match (the clone proxy asks every id this way).
    "resourceIdMatches": lambda node, value: re.fullmatch(value, node.get("resource-id") or "") is not None,
}


class _Exists:
    """uiautomator2's `exists`: truthy, and callable with a timeout."""

    def __init__(self, found):
        self._found = found

    def __bool__(self):
        return self._found

    def __call__(self, timeout=0):
        return self._found


class _Selection:
    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def exists(self):
        return _Exists(bool(self._nodes))

    @property
    def info(self):
        left, top, right, bottom = _bounds(self._nodes[0])
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}


class _Phone:
    wait_timeout = 0.0

    def __init__(self, screen):
        self.screen = screen
        self.shown = [screen]
        self.opened = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, 2220

    def __call__(self, **selector):
        nodes = etree.fromstring(SCREENS[self.screen].encode("utf-8")).iter("node")
        return _Selection([n for n in nodes if all(_UI_SELECTOR[k](n, v) for k, v in selector.items())])

    def click(self, x, y):
        for (screen, (left, top, right, bottom)), opened in DOORS.items():
            if screen == self.screen and left <= x <= right and top <= y <= bottom:
                self.screen = opened
                self.shown.append(opened)
                self.opened.append(opened)
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key, *_a):
        if key == "back" and len(self.shown) > 1:
            self.shown.pop()
            self.screen = self.shown[-1]


class _Runtime(DMInboxNavigationMixin):
    """The DM runtime as far as the opener reads it: the device a bridge hands it."""

    def __init__(self, phone):
        self.device = CloneAwareDeviceProxy(phone, PKG)


@pytest.fixture(autouse=True)
def _no_waits(monkeypatch):
    monkeypatch.setattr(navigation.time, "sleep", lambda *_: None)


def test_from_a_visited_profile_the_inbox_is_not_claimed_and_the_conversation_is_left():
    phone = _Phone("profile")
    assert _Runtime(phone).navigate_to_dm_inbox() is False
    # One tap on the look-alike, undone: no other way tried, the profile back on screen.
    assert phone.opened == ["conversation"]
    assert phone.shown == ["profile"]
    assert phone.screen == "profile"


def test_from_home_the_direct_tab_opens_the_inbox():
    phone = _Phone("home")
    assert _Runtime(phone).navigate_to_dm_inbox() is True
    assert phone.screen == "inbox"
