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

import pytest

import taktik.core.social_media.tiktok.actions.base.base_action as tiktok_base_action
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.social_media.tiktok.actions.screens_phone import Door, ScreensPhone, install_test_clock, read_captures

SCREENS = read_captures(inbox="tt4314_en_inbox.xml", opening="tt4314_en_new_followers_opening.xml",
                        page="tt4314_en_new_followers.xml")
#: The section the tap opens the page from, on the inbox dump.
SECTION = '//*[@text="New followers"]'
#: What one dump costs on the C57S, in seconds (0.2 to 1.5 s measured).
DUMP_S = 1.2


def _slow_phone(clock, load_s):
    """The inbox; after the tap on the section, the opening screen, then the page `load_s` seconds
    later (never, for None)."""
    return ScreensPhone(SCREENS, "inbox", {("inbox", SECTION): Door("page", after_s=load_s, meanwhile="opening")},
                        clock=clock, dump_s=DUMP_S)


@pytest.fixture
def clock(monkeypatch):
    return install_test_clock(monkeypatch)


@pytest.fixture(autouse=True)
def english():
    set_active_locale("en")
    yield
    set_active_locale(None)


def test_a_page_whose_rows_come_late_is_open(clock):
    """The C57S case: the rows are there four seconds after the tap, the old look had ended."""
    phone = _slow_phone(clock, load_s=4.0)

    assert DMActions(phone).open_new_followers_page() is True
    assert len(phone.taps) == 1  # the section, and nothing else
    assert phone.screen == "page"


def test_a_page_already_rendered_is_read_at_once(clock):
    """No fixed pause after the tap: the first look that finds the rows ends the wait. The tap's
    own human delay (at most half a second) comes first; the old pause added a full second."""
    phone = _slow_phone(clock, load_s=0.0)

    assert DMActions(phone).open_new_followers_page() is True
    (tapped_at,) = phone.tap_times
    first_dump_after_tap = next(at for at in phone.dumps if at >= tapped_at)
    assert first_dump_after_tap - tapped_at < 1.0


def test_a_page_that_never_comes_is_not_open_and_the_wait_is_bounded(clock):
    phone = _slow_phone(clock, load_s=None)

    assert DMActions(phone).open_new_followers_page() is False
    (tapped_at,) = phone.tap_times
    assert clock.now - tapped_at <= tiktok_base_action.SCREEN_ARRIVAL_TIMEOUT_S + 2 * DUMP_S + 1.0
