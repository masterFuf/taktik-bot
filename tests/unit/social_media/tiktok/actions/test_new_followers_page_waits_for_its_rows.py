"""`open_new_followers_page` waits for the page's rows, bounded, instead of a fixed pause.

Measured on the C57S (TikTok 43.1.4, English, 2026-10-25): the tap on « New followers » opened the
page, and `open_new_followers_page` still answered False. It paused one second, then looked for the
rows (`o0v`) for two more; on that slow phone the rows came after the look had ended. The welcome
pass and the manual follow-back then stopped on `page_unavailable`, on a page that was open.

The screens are real dumps of that phone, anonymized: its inbox; the dump taken right after the
tap, while the page opens (TikTok's window is still empty, only the status bar reads); and the
page with its rows. The phone below takes `DUMP_S` seconds for every dump and shows the rows
`load_s` seconds after the tap lands on the section (1.2 to 2.0 s in three openings measured on
that phone the same evening, more on the one that failed). The clock is the test's: nothing sleeps.
"""

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
INBOX = (FIXTURES / "tt4314_en_inbox.xml").read_text(encoding="utf-8")
OPENING = (FIXTURES / "tt4314_en_new_followers_opening.xml").read_text(encoding="utf-8")
PAGE = (FIXTURES / "tt4314_en_new_followers.xml").read_text(encoding="utf-8")
#: The section the tap opens the page from, on the inbox dump.
SECTION = '//*[@text="New followers"]'
#: What one dump costs on the C57S, in seconds (0.2 to 1.5 s measured).
DUMP_S = 1.2


def _bounds(xml, xpath):
    node = etree.fromstring(xml.encode("utf-8")).xpath(xpath)[0]
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


class _SlowPhone:
    """The inbox; after the tap on the section, the opening screen, then the page `load_s` seconds
    later (never, for None)."""

    wait_timeout = 0.0
    serial = "PHONE-1"

    def __init__(self, clock, load_s):
        self.clock = clock
        self.load_s = load_s
        self.tapped_at = None
        self.taps = []
        self.dumps = []
        self.xpath = XPathEntry(self)

    def _screen(self):
        if self.tapped_at is None:
            return INBOX
        if self.load_s is None or self.clock.now < self.tapped_at + self.load_s:
            return OPENING
        return PAGE

    def dump_hierarchy(self, *_a, **_k):
        screen = self._screen()
        self.dumps.append(self.clock.now)
        self.clock.now += DUMP_S
        return screen

    def app_current(self):
        return {"package": "com.ss.android.ugc.trill"}

    def window_size(self):
        return 576, 1280

    def click(self, x, y):
        self.taps.append((x, y))
        left, top, right, bottom = _bounds(INBOX, SECTION)
        if self.tapped_at is None and left <= x <= right and top <= y <= bottom:
            self.tapped_at = self.clock.now

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, key):
        self.taps.append(("press", key))


@pytest.fixture
def clock(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    fake_time = SimpleNamespace(time=lambda: clock.now, monotonic=lambda: clock.now,
                                perf_counter=lambda: clock.now,
                                sleep=lambda s: setattr(clock, "now", clock.now + float(s or 0)))
    for module in (dm_actions_module, tiktok_base_action, shared_base_action, snapshot_module,
                   shared_facade, tiktok_facade):
        monkeypatch.setattr(module, "time", fake_time)
    return clock


@pytest.fixture(autouse=True)
def english():
    set_active_locale("en")
    yield
    set_active_locale(None)


def test_a_page_whose_rows_come_late_is_open(clock):
    """The C57S case: the rows are there four seconds after the tap, the old look had ended."""
    phone = _SlowPhone(clock, load_s=4.0)

    assert DMActions(phone).open_new_followers_page() is True
    assert len(phone.taps) == 1  # the section, and nothing else
    assert phone.dump_hierarchy() is PAGE


def test_a_page_already_rendered_is_read_at_once(clock):
    """No fixed pause after the tap: the first look that finds the rows ends the wait. The tap's
    own human delay (at most half a second) comes first; the old pause added a full second."""
    phone = _SlowPhone(clock, load_s=0.0)

    assert DMActions(phone).open_new_followers_page() is True
    first_dump_after_tap = next(at for at in phone.dumps if at >= phone.tapped_at)
    assert first_dump_after_tap - phone.tapped_at < 1.0


def test_a_page_that_never_comes_is_not_open_and_the_wait_is_bounded(clock):
    phone = _SlowPhone(clock, load_s=None)

    assert DMActions(phone).open_new_followers_page() is False
    assert phone.tapped_at is not None
    assert clock.now - phone.tapped_at <= dm_actions_module.NEW_FOLLOWERS_PAGE_TIMEOUT_S + 2 * DUMP_S + 1.0
