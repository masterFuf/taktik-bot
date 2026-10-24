"""Opening the DM inbox answers by arrival: a visited profile's Message button is not the inbox.

Measured on a Pixel 3a (Instagram 410, in English), Lab auto-test: `dm.open_inbox`, played on the
profile of a public account, found no Direct tab, tapped the first element described "Message" -- the
profile's Message button -- and answered "DM inbox open" on an empty conversation with that account.
The next test typed into that screen (the composer had no focus: nothing landed). The production
opener (`navigate_to_dm_inbox`) returned True on every tap without looking where it had landed.

Measured on a Pixel 6 Pro (Instagram 410, Android 17, in French), Lab, 2026-10-24: `dm.open_inbox`
tapped the Direct tab of the home feed, looked for the inbox 5 s after the tap, did not see it,
pressed Back and answered "the DM inbox did not come up"; the screen captured about 2 s later was
the inbox, and the Back had not left it. The same day `dm.open_requests` answered "no requests
entry" on that inbox: its requests are a pill of the header (Tout / Principal / Général /
Invitations), not the header button the opener looked for. The English inbox (Lab corpus,
2026-09-30) has the same pills (All / Primary / General / Requests).

The screens are real dumps, anonymized: the home feed and a visited profile with its Message button
(existing fixtures), the DM inbox and the empty conversation the tap opened (the auto-test's own
captures), and the French home feed and pill inbox of the Pixel 6 Pro. The phone answers `d(...)` and
`xpath` from the screen on show, on its own clock; a tap on the Direct tab opens the inbox (on the
Pixel 6 Pro, 6 s after the tap, a Back pressed meanwhile lost in the transition), a tap on the
Message button opens the conversation, Back returns.
"""

import re
from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.wait as wait_module
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
    "home_fr": (FIXTURES / "ig410_fr_home_feed_before_dm_tab.xml").read_text(encoding="utf-8"),
    "inbox_pills_fr": (FIXTURES / "ig410_fr_dm_inbox_pills.xml").read_text(encoding="utf-8"),
}
#: What a tap opens: (screen, bounds of the element) -> (the screen it brings up, seconds it takes).
DOORS = {
    ("home", (432, 1967, 648, 2088)): ("inbox", 0.0),  # the Direct tab
    ("profile", (496, 877, 943, 965)): ("conversation", 0.0),  # the profile's Message button
    ("home_fr", (576, 2882, 864, 3036)): ("inbox_pills_fr", 6.0),  # the Direct tab, Pixel 6 Pro
}
#: The requests pill of each pill inbox (its clickable container).
REQUESTS_PILL = {
    "inbox": (725, 865, 1033, 953),
    "inbox_pills_fr": (1018, 1146, 1382, 1258),
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
    """uiautomator2's `exists`: truthy, and callable with a timeout it waits on the phone's clock."""

    def __init__(self, phone, selector):
        self._phone = phone
        self._selector = selector

    def __bool__(self):
        return bool(self._phone.nodes(self._selector))

    def __call__(self, timeout=0):
        if self:
            return True
        self._phone.clock.sleep(timeout)
        return bool(self)


class _Selection:
    def __init__(self, phone, selector):
        self._phone = phone
        self._selector = selector

    @property
    def exists(self):
        return _Exists(self._phone, self._selector)

    @property
    def info(self):
        left, top, right, bottom = _bounds(self._phone.nodes(self._selector)[0])
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

    def get_text(self):
        nodes = self._phone.nodes(self._selector)
        return nodes[0].get("text") if nodes else None


class _Clock:
    """The phone's time: what `time.time` and `time.sleep` read and spend in the code under test."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(0.0, float(seconds or 0))


class _Phone:
    wait_timeout = 0.0

    def __init__(self, screen):
        self.clock = _Clock()
        self._screen = screen
        self.shown = [screen]
        self.opened = []
        self.clicks = []
        self._coming = None  # (screen, at): a screen on its way after a tap
        self.xpath = XPathEntry(self)

    @property
    def screen(self):
        if self._coming and self.clock.now >= self._coming[1]:
            opened = self._coming[0]
            self._coming = None
            self._screen = opened
            self.shown.append(opened)
            self.opened.append(opened)
        return self._screen

    def nodes(self, selector):
        tree = etree.fromstring(SCREENS[self.screen].encode("utf-8"))
        return [n for n in tree.iter("node") if all(_UI_SELECTOR[k](n, v) for k, v in selector.items())]

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, 2220

    def __call__(self, **selector):
        return _Selection(self, selector)

    def click(self, x, y):
        self.clicks.append((self.screen, x, y))
        for (screen, (left, top, right, bottom)), (opened, delay) in DOORS.items():
            if screen == self.screen and left <= x <= right and top <= y <= bottom:
                self._coming = (opened, self.clock.now + delay)
                self.screen  # a door without delay opens at once
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key, *_a):
        # A Back pressed while a screen is coming up is lost in the transition (the Pixel 6 Pro
        # capture after the opener's Back still showed the inbox).
        if key == "back" and self._coming is None and len(self.shown) > 1:
            self.shown.pop()
            self._screen = self.shown[-1]


class _Runtime(DMInboxNavigationMixin):
    """The DM runtime as far as the opener reads it: the device a bridge hands it."""

    def __init__(self, phone):
        self.device = CloneAwareDeviceProxy(phone, PKG)


@pytest.fixture
def phone_on(monkeypatch):
    """A phone on `screen`, whose clock the opener and the shared waits read and spend."""

    def build(screen):
        phone = _Phone(screen)
        clock = SimpleNamespace(time=phone.clock.time, sleep=phone.clock.sleep)
        monkeypatch.setattr(navigation, "time", clock)
        monkeypatch.setattr(wait_module, "time", clock)
        return phone

    return build


def _inside(click, bounds):
    _screen, x, y = click
    left, top, right, bottom = bounds
    return left <= x <= right and top <= y <= bottom


def test_from_a_visited_profile_the_inbox_is_not_claimed_and_the_conversation_is_left(phone_on):
    phone = phone_on("profile")
    assert _Runtime(phone).navigate_to_dm_inbox() is False
    # One tap on the look-alike, undone: no other way tried, the profile back on screen.
    assert phone.opened == ["conversation"]
    assert phone.shown == ["profile"]
    assert phone.screen == "profile"


def test_from_home_the_direct_tab_opens_the_inbox(phone_on):
    phone = phone_on("home")
    assert _Runtime(phone).navigate_to_dm_inbox() is True
    assert phone.screen == "inbox"


def test_an_inbox_slow_to_come_up_is_waited_for_and_kept(phone_on):
    phone = phone_on("home_fr")
    assert _Runtime(phone).navigate_to_dm_inbox() is True
    assert phone.screen == "inbox_pills_fr"
    assert phone.clock.now >= 6.0


@pytest.mark.parametrize("inbox", ["inbox_pills_fr", "inbox"], ids=["fr-invitations", "en-requests"])
def test_on_a_pill_inbox_the_requests_pill_is_the_requests_entry(phone_on, inbox):
    phone = phone_on(inbox)

    opened = _Runtime(phone).open_requests_folder()

    # The pill is tapped. What it brings up has no capture yet: the screen stays as it was, and
    # the opener does not claim an arrival it cannot see.
    assert len(phone.clicks) == 1
    assert _inside(phone.clicks[0], REQUESTS_PILL[inbox])
    assert opened is False
