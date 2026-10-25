"""A TikTok page opened by a tap is said open once it is on screen, and only then.

Two faults, measured on the C57S (TikTok 43.1.4, English, 2026-10-25), and the same shape on every
opening of the inbox family.

The page was taken for another. The new-followers page was « open » as soon as rows `o0v` showed,
and the Activity page's rows are `o0v` too on 43.1.4: a tap that landed on the Activity row opened
« the new-followers page ». The message-requests page was « open » on a title id alone (`nmh`, the
title of every page, « New followers » included), on its name alone (the inbox row that opens it
reads it too) or on a conversation row (`t5a`, every row of the inbox). A page now proves itself by
its title: the title id AND the page's name, in the active language (`InboxSelectors._page_titles`),
and the new-followers page by its rows as well.

The arrival was not looked at, or looked at too soon. `open_request` answered True after a pause,
whatever had opened; the others paused a fixed second (three for the Activity page) and looked two
more. Each waits now for what proves the screen, by the common wait (`_wait_for_screen`, one photo
a turn, bounded by `SCREEN_ARRIVAL_TIMEOUT_S`, a miss logged and reported as `selector_miss`).

The screens are real captures, anonymized: the inbox, the new-followers page (and the same page
left scrolled to its suggested accounts, no row in sight) and the Activity page of the C57S that
evening (43.1.4, English), and the conversation one of its rows opens; the home
screen and the inbox of a Pixel 3a (43.1.4, French); the new-followers and message-requests pages of
a Pixel 6a on 46.6.3 (French, 2026-08-29), the inbox of the same phone on 46.9.3 with its row « Demandes
de messages », and the new-followers and Activity tabs of the page of 47.0.3 (2026-09-29). A dump
costs `DUMP_S` of the test's clock (1.2 to 2.6 s measured on the C57S); a page shows `LOAD_S` after
the tap, the screen before it showing meanwhile, which is what a slow phone does.
"""

import pytest

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.social_media.tiktok.actions.screens_phone import (
    FIXTURES,
    Door,
    ScreensPhone,
    install_test_clock,
    read_captures,
)

DUMP_S = 1.2
#: When a slow phone shows the page after the tap: past the old pause and look (about 3 s, 4 s for
#: the Activity page), within the wait.
LOAD_S = 5.0

C57S = read_captures(inbox="tt4314_en_inbox.xml", new_followers="tt4314_en_new_followers.xml",
                     no_row="tt4314_en_new_followers_scrolled_to_suggestions.xml",
                     activity="tt4314_en_activity.xml", thread="tt4314_en_dm_thread.xml")
PIXEL_3A = read_captures(home="tt4314_fr_home.xml", inbox="tt4314_fr_inbox.xml")
PIXEL_6A = read_captures(inbox="tt4693_fr_inbox_requests_row.xml", requests="tt4663_fr_message_requests.xml")

#: The new-followers pages among the captures, every version; the others are every other screen.
NEW_FOLLOWERS_PAGES = {"tt4314_en_new_followers.xml", "tt4314_en_new_followers_followed_back.xml",
                       "tt4314_fr_new_followers.xml", "tt4663_fr_new_followers.xml",
                       "tt4703_fr_new_followers.xml"}
VERSIONS = {"tt4314": "43.1.4", "tt4663": "46.6.3", "tt4693": "46.9.3", "tt4703": "47.0.3", "tt47_f": "47.0.3"}
CAPTURES = sorted(path.name for path in FIXTURES.glob("tt*.xml") if path.name[:6] in VERSIONS)

INBOX_SECTION = {"new_followers": '//*[@text="New followers"]', "activity": '//*[@text="Activity"]'}


@pytest.fixture
def clock(monkeypatch):
    return install_test_clock(monkeypatch)


@pytest.fixture
def phone_as(clock):
    """A phone on the version and language of its captures, as its connection and language
    detection leave the catalogues; back to the reference afterwards."""

    def build(version, language):
        apply_version_overrides("tiktok", version)
        set_active_locale(language)

    yield build
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


def _c57s(clock, first, doors=None):
    return ScreensPhone(C57S, first, doors, clock=clock, dump_s=DUMP_S)


# --- the new-followers page: its title and its rows, not rows alone ------------------------------


@pytest.mark.parametrize("name", CAPTURES)
def test_the_new_followers_page_is_recognised_on_its_captures_and_on_no_other_screen(phone_as, clock, name):
    """The Activity page of 43.1.4 (English and French) and of 47.0.3 has rows of the same shape;
    so do a profile and a posted video."""
    phone_as(VERSIONS[name[:6]], "en" if "_en_" in name else "fr")
    phone = ScreensPhone(read_captures(screen=name), "screen", clock=clock, dump_s=DUMP_S)

    assert DMActions(phone)._is_on_new_followers_page() is (name in NEW_FOLLOWERS_PAGES)


def test_a_tap_that_opened_the_activity_page_did_not_open_the_new_followers_page(phone_as, clock):
    """The two rows sit one above the other in the inbox; the page that opened is the one read."""
    phone_as("43.1.4", "en")
    phone = _c57s(clock, "inbox", {("inbox", INBOX_SECTION["new_followers"]): "activity"})

    assert DMActions(phone).open_new_followers_page() is False
    assert len(phone.taps) == 1


def test_a_new_followers_page_whose_title_shows_no_row_is_not_open(phone_as, clock):
    """Its title over the suggested accounts, the rows out of sight (the C57S that evening, the page
    left scrolled): a read there would list nobody."""
    phone_as("43.1.4", "en")
    phone = _c57s(clock, "inbox", {("inbox", INBOX_SECTION["new_followers"]): "no_row"})

    assert DMActions(phone).open_new_followers_page() is False


def test_the_new_followers_page_opened_slowly_is_open(phone_as, clock):
    phone_as("43.1.4", "en")
    phone = _c57s(clock, "inbox", {("inbox", INBOX_SECTION["new_followers"]): Door("new_followers", LOAD_S)})

    assert DMActions(phone).open_new_followers_page() is True


# --- the message-requests page: its title only ---------------------------------------------------


@pytest.mark.parametrize("phone_name, version, screen", [
    ("C57S", "43.1.4", "inbox"),          # its rows are `t5a`, the requests page's row
    ("C57S", "43.1.4", "new_followers"),  # its title is `nmh`
    ("6a", "46.9.3", "inbox"),            # its row reads « Demandes de messages »
])
def test_the_screens_the_requests_page_is_opened_from_are_not_the_page(phone_as, clock, phone_name, version, screen):
    language = "en" if phone_name == "C57S" else "fr"
    phone_as(version, language)
    phone = ScreensPhone(C57S if phone_name == "C57S" else PIXEL_6A, screen, clock=clock)

    assert DMActions(phone)._is_on_message_requests_page() is False


def test_the_requests_page_is_recognised_by_its_title(phone_as, clock):
    phone_as("46.6.3", "fr")
    phone = ScreensPhone(PIXEL_6A, "requests", clock=clock)

    assert DMActions(phone)._is_on_message_requests_page() is True


def _6a_inbox(clock, after_s):
    """The inbox of 46.9.3, whose row opens the requests page (a capture of 46.6.3: the title the
    46.9.3 inherits from the overrides; no 46.9.3 capture of the page was kept)."""
    row = '//*[@clickable="true"][.//*[@text="Demandes de messages"]]'
    return ScreensPhone(PIXEL_6A, "inbox", {("inbox", row): Door("requests", after_s)}, clock=clock,
                        dump_s=DUMP_S, package="com.zhiliaoapp.musically", size=(1080, 2400))


def test_a_requests_page_that_never_comes_is_not_open(phone_as, clock):
    """The inbox stays on screen: its row read as the page's title."""
    phone_as("46.9.3", "fr")
    phone = _6a_inbox(clock, after_s=None)

    assert DMActions(phone).open_message_requests_page() is False
    assert len(phone.taps) == 1


def test_a_requests_page_that_comes_slowly_is_open(phone_as, clock):
    phone_as("46.9.3", "fr")
    phone = _6a_inbox(clock, after_s=LOAD_S)

    assert DMActions(phone).open_message_requests_page() is True


def test_a_request_whose_tap_opened_nothing_is_not_open(phone_as, clock):
    """The request's screen is the one that offers to accept or delete it; the requests page still
    showing is not it. (No capture of an open request: opening one may tell its sender it was
    seen, so the screen that does open is not tested here.)"""
    phone_as("46.6.3", "fr")
    phone = ScreensPhone(PIXEL_6A, "requests", clock=clock, dump_s=DUMP_S,
                         package="com.zhiliaoapp.musically", size=(1080, 2400))

    assert DMActions(phone).open_request("user_3") is False
    assert len(phone.taps) == 1


# --- the inbox, a conversation, the Activity page: reached slowly is reached ---------------------


def test_the_inbox_shown_slowly_after_its_tab_is_reached(phone_as, clock):
    phone_as("43.1.4", "fr")
    tab = '//*[contains(@resource-id, ":id/mkr")]'
    phone = ScreensPhone(PIXEL_3A, "home", {("home", tab): Door("inbox", LOAD_S)}, clock=clock,
                         dump_s=DUMP_S, package="com.zhiliaoapp.musically", size=(1080, 2220))

    assert DMActions(phone).navigate_to_inbox() is True
    assert len(phone.taps) == 1


def test_a_conversation_shown_slowly_after_its_row_is_open(phone_as, clock):
    phone_as("43.1.4", "en")
    row = '//*[contains(@resource-id, ":id/t5a")][.//*[@text="‎name_38"]]'
    phone = _c57s(clock, "inbox", {("inbox", row): Door("thread", LOAD_S)})

    assert DMActions(phone).click_conversation("name_38") is True
    assert len(phone.taps) == 1


def test_the_inbox_shown_slowly_after_the_back_of_a_conversation_is_reached(phone_as, clock):
    phone_as("43.1.4", "en")
    phone = _c57s(clock, "thread", {("thread", '//*[@content-desc="Back"]'): Door("inbox", LOAD_S)})

    assert DMActions(phone).go_back_to_inbox() is True
    assert len(phone.taps) == 1


def test_the_activity_page_shown_slowly_after_its_row_is_open(phone_as, clock):
    phone_as("43.1.4", "en")
    phone = _c57s(clock, "inbox", {("inbox", INBOX_SECTION["activity"]): Door("activity", LOAD_S)})

    assert ActivityActions(phone).open_activity(expand=False) is True
    assert len(phone.taps) == 1


def test_an_activity_page_that_never_comes_is_not_open_and_the_wait_is_bounded(phone_as, clock):
    import taktik.core.social_media.tiktok.actions.base.base_action as tiktok_base_action

    phone_as("43.1.4", "en")
    phone = _c57s(clock, "inbox", {("inbox", INBOX_SECTION["activity"]): Door("activity", None)})

    assert ActivityActions(phone).open_activity(expand=False) is False
    (tapped_at,) = phone.tap_times
    assert clock.now - tapped_at <= tiktok_base_action.SCREEN_ARRIVAL_TIMEOUT_S + 2 * DUMP_S + 1.0
