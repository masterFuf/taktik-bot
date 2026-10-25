"""The scraping reads a list until it ends, by the end `ScrollEndDetector` tells from the rows SHOWN.

Two copies of the list loop live in the scraping. `_scrape_list` (followers, following, the likers
of a target's post or of a hashtag's posts, commenters) fed its detector with every username seen
since the start: "a page identical to the one before" then meant "nothing new", and a screen
without any row never reached the detector at all. On a list that shows nothing more, it scrolled
until the session's time limit. `_extract_usernames_from_likers_list` (the likers of a post URL)
stopped after three rounds without a new username, and so stopped on a list that still moved.

Now `_scrape_list` hears the rows shown by its first reading and by each reading that follows a
scroll (a second reading of a screen nothing scrolled says nothing, journal IG-FEED-031), with the
thresholds of its strategy: a likers sheet ends like the reading of the likers of the runs
(`likers_list_end_detector`, two scrolls that change nothing). The likers of a post URL are read by
that reading itself (`extract_usernames_from_likers_popup`).

The screens are the real likers sheets of `likers_sheet_phone` (C57 S, Instagram 410 in English);
the host is the scraping workflow's class, with its production detection, scroll and extractors on
that phone. The base and the events of the app are the only stand-ins.
"""

import time
from types import SimpleNamespace

import pytest
from loguru import logger

import taktik.core.social_media.instagram.workflows.scraping.list_scraping as list_scraping
from unit.social_media.instagram.services.likers_sheet_phone import LONG_LIST, TWO_LIKERS, LikersSheetPhone
from unit.social_media.instagram.services.profile_posts_phone import PKG, capture
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
from taktik.core.social_media.instagram.actions.atomic.scroll import ScrollActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow

#: Laps of the loop after which the test's session gives up, as the time limit of a run would.
LAPS_OF_A_SESSION = 100


@pytest.fixture(autouse=True)
def _english_phone_no_waits(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    monkeypatch.setattr(list_scraping, "IPCEmitter", SimpleNamespace(
        emit_profile_skipped=lambda *_a, **_k: None,
        emit_scraping_profile_visit=lambda *_a, **_k: None,
        emit_profile_captured=lambda *_a, **_k: None,
    ))
    set_active_locale("en")
    yield
    set_active_locale(None)


def _scraping_on(phone):
    device = DeviceFacade(CloneAwareDeviceProxy(phone, PKG))
    workflow = object.__new__(ScrapingWorkflow)
    workflow.device = device
    workflow.logger = logger.bind(module="test-scraping-lists")
    workflow.detection_actions = DetectionActions(device)
    workflow.scroll_actions = ScrollActions(device)
    workflow.ui_extractors = InstagramUIExtractors(device)
    workflow.config = {"rescrape_after_days": 0}  # no base: every row is new to the scraping
    workflow.scraped_profiles = []
    workflow._save_profile_immediately = lambda *_a, **_k: None
    workflow.laps = 0

    def session_goes_on():
        workflow.laps += 1
        return workflow.laps <= LAPS_OF_A_SESSION

    workflow._should_continue = session_goes_on
    return workflow


def _moved(first_screen, phone):
    shown = [first_screen] + phone.likers_after_each_drag_up
    return [after != before for before, after in zip(shown, shown[1:])]


def test_the_likers_of_a_post_scraped_end_two_scrolls_after_a_list_of_two():
    from taktik.core.social_media.instagram.workflows.scraping.list_strategy import make_likers_strategy

    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    workflow = _scraping_on(phone)

    scraped = workflow._scrape_list(max_count=10, source_type="POST_LIKERS", source_name="target",
                                    strategy=make_likers_strategy(workflow))

    assert sorted(p["username"] for p in scraped) == phone.likers_shown()
    drags_up = len(phone.likers_after_each_drag_up)
    assert drags_up == 2, f"{drags_up} scroll(s) down a list of two likers that no longer moves"


def test_reading_a_screen_again_after_each_profile_is_not_a_scroll_that_changed_nothing():
    from taktik.core.social_media.instagram.workflows.scraping.list_strategy import make_likers_strategy

    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    workflow = _scraping_on(phone)
    workflow._capture_profile_on_screen = lambda **_kw: None  # each profile opened is kept

    scraped = workflow._scrape_list(max_count=10, source_type="POST_LIKERS", source_name="target",
                                    enrich_on_the_fly=True, strategy=make_likers_strategy(workflow))

    assert sorted(p["username"] for p in scraped) == phone.likers_shown()
    assert len(phone.taps) == 2
    drags_up = len(phone.likers_after_each_drag_up)
    assert drags_up == 2, f"{drags_up} scroll(s) down a list of two likers, each profile opened from it"


def test_a_list_that_shows_no_row_any_more_ends_instead_of_scrolling_until_the_time_limit():
    phone = LikersSheetPhone(capture(LONG_LIST), moves=True)
    first_screen = phone.likers_shown()
    workflow = _scraping_on(phone)

    scraped = workflow._scrape_list(max_count=50, source_type="FOLLOWERS", source_name="target")

    assert workflow.laps <= LAPS_OF_A_SESSION, "the scraping ran until the session's time limit"
    assert len(scraped) == len(first_screen)
    moved = _moved(first_screen, phone)
    # The list moved until it showed no row, then the default end: 8 empty readings in a row.
    assert moved[-7:] == [False] * 7 and all(moved[:-7]), f"likers after each scroll: {phone.likers_after_each_drag_up}"


def test_the_likers_of_a_post_url_are_read_while_their_list_moves():
    phone = LikersSheetPhone(capture(LONG_LIST), moves=True)
    first_screen = phone.likers_shown()
    workflow = _scraping_on(phone)

    likers = workflow._extract_usernames_from_likers_list(10)

    assert sorted(likers) == first_screen
    moved = _moved(first_screen, phone)
    # Every scroll moved the list until it was empty, then two scrolls showed it still: the end.
    assert moved[-2:] == [False, False], f"likers after each scroll: {phone.likers_after_each_drag_up}"
    assert all(moved[:-2]) and len(moved) > 2, f"likers after each scroll: {phone.likers_after_each_drag_up}"


def test_the_likers_of_a_post_url_end_two_scrolls_after_a_list_of_two():
    phone = LikersSheetPhone(capture(TWO_LIKERS), moves=False)
    workflow = _scraping_on(phone)

    likers = workflow._extract_usernames_from_likers_list(10)

    assert sorted(likers) == phone.likers_shown()
    assert len(phone.likers_after_each_drag_up) == 2


def test_the_session_clock_stops_the_reading_of_the_likers_of_a_post_url():
    phone = LikersSheetPhone(capture(LONG_LIST), moves=True)
    workflow = _scraping_on(phone)
    workflow._should_continue = lambda: False

    assert workflow._extract_usernames_from_likers_list(10) == []
    assert phone.drags == []
