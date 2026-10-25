"""A TikTok inbox row is acted on only when its name is the name asked for (`same_shown_name`).

The conversation a reply goes into, the wave sent from the inbox and the follower followed back
were each picked by inclusion: the first row whose name held the name asked for, or was held by
it. Measured on a C57S (TikTok 43.1.4, English, 2026-10-25): « demo_fan🦋 » sits right under
« 1NE demo_fan ft AP », so `click_conversation("demo_fan")` opened the second account's
conversation, the first row that held the name.

The screens are real dumps, anonymized (`scripts/lab/anonymize_dump.py`, the same word gets the same
placeholder, so « demo_fan » reads `name_33`name_34` in both rows): the English inbox of that
phone and the conversation one of its rows opens, and the French new-followers page of a Pixel 3a
(43.1.4). The phone answers `xpath` through uiautomator2's own engine and `d(resourceIdMatches=...)`
from the same dump; what a tap opens is written in `doors`, per test.
"""

import re
from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.shared.device.facade as shared_facade
import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions as dm_actions_module
import taktik.core.social_media.tiktok.actions.base.base_action as tiktok_base_action
import taktik.core.social_media.tiktok.actions.base.device_facade as tiktok_facade
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
FILES = {
    "inbox": "tt4314_en_inbox.xml",
    "thread": "tt4314_en_dm_thread.xml",
    "new_followers": "tt4314_fr_new_followers.xml",
}
SCREENS = {name: (FIXTURES / file).read_text(encoding="utf-8") for name, file in FILES.items()}

#: The rows of the inbox, by the name each shows (the anonymiser's words).
GROUP_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200e...... name_33`name_34 name_35 ...."]]'
BUTTERFLY_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200ename_33`name_34.."]]'
GRANNY_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200ename_38"]]'
AUSTIN_ROW = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="\u200ename_40"]]'
#: The new-followers page: the row of user_1, who shows « Suivre en retour », and its button.
USER_1_FOLLOW_BACK = ('//*[contains(@resource-id, ":id/o0v")][.//*[@text="\u200e\u2068user_1\u2069"]]'
                      '//*[contains(@resource-id, ":id/rdh")]')


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


def _node(screen, xpath):
    return etree.fromstring(SCREENS[screen].encode("utf-8")).xpath(xpath)[0]


def _inside(tap, screen, xpath):
    left, top, right, bottom = _bounds(_node(screen, xpath))
    return tap[0] == screen and left <= tap[1] <= right and top <= tap[2] <= bottom


class _Selection:
    """`d(resourceIdMatches=...)` as `_find_all_by_rid` asks it: `exists`, `count`, an index, the
    text, the bounds, a click."""

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

    def get_text(self):
        return self._nodes[0].get("text")

    @property
    def info(self):
        left, top, right, bottom = _bounds(self._nodes[0])
        return {"bounds": {"left": left, "top": top, "right": right, "bottom": bottom}}

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
        return {"package": "com.ss.android.ugc.trill"}

    def window_size(self):
        return 576, 1280

    def __call__(self, resourceIdMatches):
        nodes = etree.fromstring(SCREENS[self.screen].encode("utf-8")).iter("node")
        return _Selection(self, [n for n in nodes
                                 if re.fullmatch(resourceIdMatches, n.get("resource-id") or "")])

    def click(self, x, y):
        self.taps.append((self.screen, x, y))
        for (screen, xpath), opened in self.doors.items():
            if screen == self.screen and _inside((screen, x, y), screen, xpath):
                self.screen = opened
                return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key):
        self.taps.append((self.screen, "press", key))


@pytest.fixture(autouse=True)
def _clock(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now,
                                perf_counter=lambda: clock.now,
                                sleep=lambda s: setattr(clock, "now", clock.now + float(s or 0)))
    for module in (dm_actions_module, tiktok_base_action, shared_base_action, snapshot_module,
                   shared_facade, tiktok_facade):
        monkeypatch.setattr(module, "time", fake_time)


@pytest.fixture
def english():
    set_active_locale("en")
    yield
    set_active_locale(None)


@pytest.fixture
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


# --- the conversation a reply goes into -----------------------------------------------------------


@pytest.mark.parametrize("asked", [
    "name_33`name_34",  # the butterfly row's name without its emoji, held by the group row above it
    "name_3",           # the beginning of every row name_33..., name_38
    "name_35",          # a word of the group row
])
def test_a_name_a_row_only_holds_opens_no_conversation(asked, english):
    phone = _Phone("inbox", {("inbox", GROUP_ROW): "thread", ("inbox", GRANNY_ROW): "thread"})

    assert DMActions(phone).click_conversation(asked) is False
    assert phone.taps == []


def test_the_row_of_the_name_opens_its_conversation(english):
    phone = _Phone("inbox", {("inbox", GRANNY_ROW): "thread"})

    assert DMActions(phone).click_conversation("name_38") is True
    (tap,) = phone.taps
    assert _inside(tap, "inbox", GRANNY_ROW)


def test_a_name_read_with_its_emoji_opens_the_row_the_dump_shows_with_two_dots(english):
    """The selector API returns « demo_fan🦋 »; the dump, and so the conversation header a read
    returns, « demo_fan.. ». A reply holds either."""
    phone = _Phone("inbox", {})

    DMActions(phone).click_conversation("name_33`name_34\U0001f98b")

    (tap,) = phone.taps
    assert _inside(tap, "inbox", BUTTERFLY_ROW)


def test_the_handle_is_read_only_off_the_thread_of_the_name(english):
    phone = _Phone("inbox", {("inbox", GRANNY_ROW): "thread",
                             ("thread", '//*[@content-desc="Back"]'): "inbox"})

    assert DMActions(phone).resolve_conversation_handle("\u200ename_38") == "user_4"
    assert _inside(phone.taps[0], "inbox", GRANNY_ROW)


# --- the wave sent from the inbox -----------------------------------------------------------------


def test_a_wave_goes_to_no_row_whose_name_only_starts_with_the_name(english):
    phone = _Phone("inbox", {})

    assert DMActions(phone).say_hello("name_4") is False
    assert phone.taps == []


def test_a_wave_is_tapped_in_the_row_of_the_name(english):
    """Only the row is asserted: on this screen (43.1.4) the row offers no wave button at all, and
    its last clickable is the camera shortcut, an open question of its own."""
    phone = _Phone("inbox", {})

    DMActions(phone).say_hello("name_40")

    assert phone.taps and all(_inside(tap, "inbox", AUSTIN_ROW) for tap in phone.taps)


# --- the follower followed back -------------------------------------------------------------------


def test_no_follower_is_followed_back_for_a_name_that_only_starts_theirs(french):
    phone = _Phone("new_followers", {})

    assert DMActions(phone).follow_back("user") is False
    assert phone.taps == []


def test_the_follower_of_the_name_is_followed_back(french):
    phone = _Phone("new_followers", {})

    DMActions(phone).follow_back("user_1")

    (tap,) = phone.taps
    assert _inside(tap, "new_followers", USER_1_FOLLOW_BACK)


def test_a_follow_back_is_offered_only_to_the_row_of_the_name(french):
    phone = _Phone("new_followers", {})

    followers = DMActions(phone).get_new_followers()

    assert [(f["username"], f["can_follow_back"]) for f in followers][1] == ("user_1", True)
    assert phone.taps == []
