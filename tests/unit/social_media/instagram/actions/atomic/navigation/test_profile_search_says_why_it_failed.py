"""The profile search says why it opened nobody, and never calls a slow search an empty one.

`navigate_to_profile` answered False alike for an account the search does not list and for a
search still loading: both read "Could not find @... in search results" after 5 s. On 2026-11-20
(Pixel 6a, Instagram 447, French, network throttled) an account that exists was declared absent
that way: the results showed grey loading rows for the whole wait. The same captures tell the three
screens apart on one tree, anonymized here (`ig447_fr_search_results_*`):
- `loading_existing_account` (`user_1`, an account that exists, 5.6 kbit/s) and
  `loading_absent_account` (`user_2`, a handle nobody has, 2.4 kbit/s): grey rows only;
- `loaded_absent_account` (`user_3`, nobody, normal network): the row of the query alone;
- `loaded_account_listed` (`name_16`, 128 kbit/s): the row of the query, then three account rows,
  the second one `name_16`. Its tap opened nothing: the list stayed on screen 35 s.
The failure is kept in `last_profile_navigation_failure`; "not found" only from an answered list,
and with the deep link tried, only when that link shows no profile either.
"""

import pytest

import taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation as search_navigation
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.instagram.actions.atomic.navigation.deep_link_navigation import (
    DeepLinkNavigationMixin,
)
from taktik.core.social_media.instagram.actions.atomic.navigation.search_results import (
    ProfileNavigationFailure,
    ProfileNavigationFailureReason as Reason,
    SearchResultsState as State,
    read_search_results,
)

from search_screens_phone import DIRECT_RUN, FIXTURES, SEARCH_410, SEARCH_447, selectors_of
from test_profile_search_opens_only_the_asked_account import _navigation, phone_on  # noqa: F401 (fixture)


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


LOADING_EXISTING = _screen("ig447_fr_search_results_loading_existing_account.xml")
LOADING_ABSENT = _screen("ig447_fr_search_results_loading_absent_account.xml")
LOADED_ABSENT = _screen("ig447_fr_search_results_loaded_absent_account.xml")
LOADED_LISTED = _screen("ig447_fr_search_results_loaded_account_listed.xml")


@pytest.mark.parametrize("screen, handle, state", [
    (LOADING_EXISTING, "user_1", State.LOADING),
    (LOADING_ABSENT, "user_2", State.LOADING),
    (LOADED_ABSENT, "user_3", State.NOT_LISTED),
    (LOADED_LISTED, "name_16", State.LISTED),
    (LOADED_LISTED, "user_4", State.LISTED),
    (LOADED_LISTED, "name_1x", State.UNRECOGNIZED),
], ids=["loading-existing", "loading-absent", "answered-absent", "answered-listed", "a-neighbour-listed",
        "another-query"])
def test_one_tree_tells_loading_absent_and_listed_apart_on_447(screen, handle, state):
    with selectors_of(SEARCH_447):
        assert read_search_results(ScreenSnapshot(screen), handle) is state


def test_the_410_results_read_the_same_way():
    """`ig410_fr_account_search_results`: the query `name_1`, account rows `user_1` to `user_4`. The
    results of another query are no answer for a handle: not recognized, never "not listed"."""
    photo = ScreenSnapshot(SEARCH_410.results)
    with selectors_of(SEARCH_410):
        assert read_search_results(photo, "user_2") is State.LISTED
        assert read_search_results(photo, "user_9") is State.UNRECOGNIZED


def test_without_the_447_loading_rows_a_loading_screen_is_not_read_as_an_answer():
    """The baseline knows no loading row: grey rows are no screen it recognizes, never "not listed"."""
    with selectors_of(SEARCH_410):
        assert read_search_results(ScreenSnapshot(LOADING_ABSENT), "user_2") is State.UNRECOGNIZED


@pytest.fixture
def no_waiting(monkeypatch):
    monkeypatch.setattr(search_navigation, "SEARCH_RESULTS_TIMEOUT_S", 0.0, raising=False)
    monkeypatch.setattr(search_navigation, "PROFILE_LOAD_TIMEOUT_S", 0.0)


@pytest.mark.parametrize("screen, handle", [(LOADING_EXISTING, "user_1"), (LOADING_ABSENT, "user_2")],
                         ids=["existing", "absent"])
def test_a_search_still_loading_is_slow_never_not_found(phone_on, no_waiting, screen, handle):
    phone = phone_on(SEARCH_447, results_of={handle: screen})
    navigation = _navigation(phone)

    assert navigation.navigate_to_profile(handle, force_search=True) is False

    failure = navigation.last_profile_navigation_failure
    assert (failure.route, failure.reason) == ("search", Reason.SEARCH_SLOW)
    assert failure.search_slow and not failure.account_not_found
    assert phone.rows_tapped() == []


def test_an_answered_list_without_the_account_is_not_found(phone_on, no_waiting):
    phone = phone_on(SEARCH_447, results_of={"user_3": LOADED_ABSENT})
    navigation = _navigation(phone)

    assert navigation.navigate_to_profile("user_3", force_search=True) is False

    assert navigation.last_profile_navigation_failure.account_not_found


@pytest.fixture
def deep_link_verified(monkeypatch, phone_on):
    """The deep link as production ends it: the phone shows its page, the profile check reads it."""
    def build(screens, **options):
        phone = phone_on(screens, **options)
        monkeypatch.setattr(
            DeepLinkNavigationMixin, "_navigate_via_deep_link",
            lambda nav, username, *_a, **_k: phone.follows_deep_link(username)
            or nav._verify_profile_navigation(username))
        return phone

    return build


def test_not_found_with_the_deep_link_needs_its_page_to_show_no_profile(deep_link_verified, no_waiting):
    """`user_8`'s deep link opened an empty profile frame (the direct run of 2026-11-17)."""
    phone = deep_link_verified(
        SEARCH_447, results_of={"user_3": LOADED_ABSENT},
        deep_link_opens={"user_3": (DIRECT_RUN.deep_link_page_of_absent, None)})
    navigation = _navigation(phone)

    assert navigation.navigate_to_profile("user_3") is False

    assert phone.deep_links == ["user_3"]
    failure = navigation.last_profile_navigation_failure
    assert (failure.route, failure.reason) == ("search", Reason.NOT_LISTED)


def test_a_slow_search_stays_slow_when_the_deep_link_shows_no_profile(deep_link_verified, no_waiting):
    phone = deep_link_verified(
        SEARCH_447, results_of={"user_1": LOADING_EXISTING},
        deep_link_opens={"user_1": (DIRECT_RUN.deep_link_page_of_absent, None)})
    navigation = _navigation(phone)

    assert navigation.navigate_to_profile("user_1") is False

    assert navigation.last_profile_navigation_failure.reason is Reason.SEARCH_SLOW


def test_a_tap_that_opens_nothing_is_said_and_tapped_again_on_the_username(phone_on, no_waiting):
    """The row of `name_16` is tapped, the list stays: tapped once more, on its username, then the
    failure is the tap's, not a profile without a handle."""
    phone = phone_on(SEARCH_447, results_of={"name_16": LOADED_LISTED})
    navigation = _navigation(phone)

    assert navigation.navigate_to_profile("name_16", force_search=True) is False

    assert phone.rows_tapped() == ["name_16", "name_16"]
    username_box = (211, 615, 423, 662)
    assert phone.tap_zones[-1][1] == username_box
    assert navigation.last_profile_navigation_failure.reason is Reason.TAP_NO_EFFECT


def test_a_success_leaves_no_failure(phone_on):
    phone, opened = phone_on(SEARCH_447), []
    navigation = _navigation(phone, opened)
    navigation.last_profile_navigation_failure = ProfileNavigationFailure("search", Reason.NOT_LISTED)

    assert navigation.navigate_to_profile("user_2", force_search=True) is True

    assert navigation.last_profile_navigation_failure is None


def test_the_search_waits_for_the_list_to_load_then_reads_its_answer(phone_on, monkeypatch):
    """The grey rows of the first read, then the answer (the throttled network let go, as it was on
    the phone): the answer is what is read, not the loading."""
    monkeypatch.setattr(search_navigation, "SEARCH_RESULTS_POLL_MS", 1)
    phone = phone_on(SEARCH_447, results_of={"user_3": LOADING_ABSENT})
    shown = phone.dump_hierarchy

    def network_back(*args, **kwargs):
        screen = shown(*args, **kwargs)
        if screen is LOADING_ABSENT:
            phone.screen = LOADED_ABSENT
        return screen

    phone.dump_hierarchy = network_back
    navigation = _navigation(phone)

    assert navigation.navigate_to_profile("user_3", force_search=True) is False

    assert navigation.last_profile_navigation_failure.reason is Reason.NOT_LISTED
