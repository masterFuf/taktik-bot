"""A conversation is opened from the DM inbox's rows only, from the row of exactly the name asked
for, and is open only once it is on screen.

Measured on a Pixel 6a (Instagram 447, French), 2026-10-25, with the Lab's `dm.open_thread` (the
production `open_conversation`) run while the search results of the handle were on screen: no
inbox row matched, the last strategy looked for the handle as `textContains` anywhere on screen,
tapped the search field that held it, and answered "open=True" without looking at what came up.

The row was also chosen by inclusion: a name asked for opened the first row whose name held it, or
was held by it (« bob » opened « bobby », and the reply that followed went into bobby's conversation).
A row is now the one whose name is the name asked for, case and spaces aside (`same_shown_name`).

The screens are real dumps, anonymized: those search results (447), an inbox of 410 in French with a
conversation of the same phone, and an inbox of 447 in French (Compose rows, their name in their
digest) with a conversation of 447. The phone answers `xpath` through uiautomator2's own
engine and `d(resourceId=...)`, `d(textContains=...)` from the same dump; what a tap opens is
written in `doors`, per test.
"""

import re
from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.wait as wait_module
import taktik.core.social_media.instagram.workflows.dm.conversation_navigation as conversation_navigation
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.workflows.dm.conversation_navigation import (
    DMConversationNavigationMixin,
)
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
FILES = {
    "search_results": "ig447_fr_search_results_account.xml",
    "inbox": "ig410_fr_dm_inbox_pills.xml",
    "conversation": "ig410_fr_dm_thread.xml",
    "inbox_447": "ig447_fr_dm_inbox_pills.xml",
    "conversation_447": "ig447_fr_dm_thread.xml",
}
SCREENS = {name: (FIXTURES / file).read_text(encoding="utf-8") for name, file in FILES.items()}
HANDLE = "user_1"  # the handle the search results show, as the anonymiser named it
ROW_NAME = "name_41"  # an inbox row's name, as the anonymiser named it
ROW = ('//*[@resource-id="com.instagram.android:id/row_inbox_username"][@text="name_41"]'
       '/ancestor::*[@resource-id="com.instagram.android:id/row_inbox_container"][1]')
#: The 447 inbox shows the rows of user_10 and user_11, and none of user_1.
ROW_447 = '//*[@content-desc="user_10, Envoyé il y a 1 h"]'


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


_UI_SELECTOR = {
    "resourceId": lambda node, value: node.get("resource-id") == value,
    "resourceIdMatches": lambda node, value: re.fullmatch(value, node.get("resource-id") or "") is not None,
    "textContains": lambda node, value: value in (node.get("text") or ""),
}


class _Selection:
    """`d(...)` as the opener asks it: `exists`, `count`, an index, `child`, the text, the bounds."""

    def __init__(self, phone, nodes):
        self._phone = phone
        self._nodes = nodes

    @property
    def exists(self):
        return bool(self._nodes)

    @property
    def count(self):
        return len(self._nodes)

    def __getitem__(self, index):
        return _Selection(self._phone, [self._nodes[index]])

    def child(self, **selector):
        return _Selection(self._phone, [n for n in self._nodes[0].iter("node")
                                        if all(_UI_SELECTOR[k](n, v) for k, v in selector.items())])

    def get_text(self):
        return self._nodes[0].get("text")

    @property
    def info(self):
        left, top, right, bottom = _bounds(self._nodes[0])
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom},
                "contentDescription": self._nodes[0].get("content-desc")}

    def click(self):
        left, top, right, bottom = _bounds(self._nodes[0])
        self._phone.click((left + right) // 2, (top + bottom) // 2)


class _Phone:
    wait_timeout = 0.0
    serial = "PHONE-1"

    def __init__(self, screen, doors):
        self.screen = screen
        self.doors = doors
        self.taps = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1440, 3120

    def __call__(self, **selector):
        nodes = etree.fromstring(SCREENS[self.screen].encode("utf-8")).iter("node")
        return _Selection(self, [n for n in nodes if all(_UI_SELECTOR[k](n, v) for k, v in selector.items())])

    def click(self, x, y):
        self.taps.append((self.screen, x, y))
        for (screen, xpath), opened in self.doors.items():
            node = etree.fromstring(SCREENS[screen].encode("utf-8")).xpath(xpath)[0]
            left, top, right, bottom = _bounds(node)
            if screen == self.screen and left <= x <= right and top <= y <= bottom:
                self.screen = opened
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)


class _Runtime(DMConversationNavigationMixin):
    """The DM runtime as far as the opener reads it: the device a bridge hands it."""

    def __init__(self, phone):
        self.device = CloneAwareDeviceProxy(phone, PKG)


@pytest.fixture
def ig_447():
    """The selectors as a phone on 447 gets them at connect; the baseline put back after."""
    from taktik.core.compat.selectors.setup import apply_version_overrides, baseline_version

    apply_version_overrides("instagram", "447.0.0.55.81")
    yield
    apply_version_overrides("instagram", baseline_version("instagram"))


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now,
                                sleep=lambda s: setattr(clock, "now", clock.now + float(s or 0)))
    for module in (conversation_navigation, wait_module):
        monkeypatch.setattr(module, "time", fake_time)
    # A scroll is a gesture too: recorded, the screen does not move.
    scrolls = []
    monkeypatch.setattr(conversation_navigation, "human_scroll_raw", lambda *_a, **_k: scrolls.append(1))
    return scrolls


def test_off_the_inbox_nothing_is_tapped_nor_scrolled(_clock):
    """The Lab run of 2026-10-25: the handle sat in the search field of the search results."""
    phone = _Phone("search_results", {})

    assert _Runtime(phone).open_conversation(HANDLE) is False
    assert phone.taps == [] and _clock == []


def test_the_row_of_the_name_opens_its_conversation():
    phone = _Phone("inbox", {("inbox", ROW): "conversation"})

    assert _Runtime(phone).open_conversation(ROW_NAME) is True
    (tap,) = phone.taps
    assert tap[0] == "inbox"


def test_a_row_tap_that_opens_no_conversation_is_no_open_conversation_and_nothing_else_is_tapped():
    phone = _Phone("inbox", {})

    assert _Runtime(phone).open_conversation(ROW_NAME) is False
    assert len(phone.taps) == 1


@pytest.mark.parametrize("asked", [
    "name_4",     # the beginning of the rows name_41 and name_42 name_43
    "name_28",    # the first word of the row name_28 name_29
    "name_410",   # holds the row name_41
])
def test_a_name_that_only_holds_or_starts_a_row_name_opens_no_conversation(asked, _clock):
    """No row of the inbox is the name asked for: nothing is tapped, whatever the rows hold."""
    phone = _Phone("inbox", {("inbox", ROW): "conversation"})

    assert _Runtime(phone).open_conversation(asked) is False
    assert phone.taps == []


def test_the_name_asked_for_is_compared_case_and_spaces_aside():
    phone = _Phone("inbox", {("inbox", ROW): "conversation"})

    assert _Runtime(phone).open_conversation(" Name_41 ") is True
    assert len(phone.taps) == 1


def test_on_447_a_handle_that_starts_another_opens_no_conversation(ig_447, _clock):
    """The 447 rows give their name in their digest only (« user_10, Envoyé il y a 1 h »)."""
    phone = _Phone("inbox_447", {("inbox_447", ROW_447): "conversation_447"})

    assert _Runtime(phone).open_conversation("user_1") is False
    assert phone.taps == []


def test_on_447_the_row_of_the_handle_opens_its_conversation(ig_447):
    phone = _Phone("inbox_447", {("inbox_447", ROW_447): "conversation_447"})

    assert _Runtime(phone).open_conversation("user_10") is True
    assert phone.screen == "conversation_447" and len(phone.taps) == 1
