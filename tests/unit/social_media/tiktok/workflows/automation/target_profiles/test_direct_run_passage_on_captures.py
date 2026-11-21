"""The passage of a TikTok « Ces comptes » run from one profile to the next, on real captures.

Captured on a Pixel 6a, TikTok 47.0.3 in French, during a direct run of three handles (a profile, an
absent handle, a verified account), anonymised. Between two profiles the loop goes back to the feed
(`return_to_tiktok_home`), then searches the next handle and opens its row of the Users tab, then
checks the profile it landed on is that handle's (`_landed_on_profile_of`).

Measured on that run: the verified account's header reads `@tiktok` followed by U+FFFC, the
placeholder of the inline badge, so the check refused the right profile as "wrong profile" and the
run reported it not found.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.tiktok.actions.atomic.navigation.search_actions import SearchActions
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_home
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


HOME = _capture("tt4703_fr_direct_home_between_profiles.xml")
PROFILE_LEFT = _capture("tt4703_fr_direct_profile_left.xml")
USERS_ABSENT = _capture("tt4703_fr_direct_users_absent_handle.xml")
USERS_VERIFIED = _capture("tt4703_fr_direct_users_verified_account.xml")
PROFILE_VERIFIED = _capture("tt4703_fr_direct_profile_verified_badge.xml")
SEARCH_FIELD = _capture("tt4703_fr_search_field.xml")
RESULTS_TOP = _capture("tt4703_fr_search_top_results.xml")


class _Phone:
    """The app's back stack: back pops the top screen, and nothing else moves."""

    wait_timeout = 0.0

    def __init__(self, *stack):
        self.stack = list(stack)
        self.xpath = XPathEntry(self)
        self.presses = []

    def dump_hierarchy(self, *_a, **_k):
        return self.stack[-1]

    def snapshot(self, *_a, **_k):
        # The facade's photo of the screen: one dump.
        return ScreenSnapshot(self.stack[-1])

    def press(self, key):
        self.presses.append(key)
        if key == "back" and len(self.stack) > 1:
            self.stack.pop()

    def click(self, _x, _y):
        pass


class _Log:
    def __init__(self):
        self.errors = []

    def error(self, message, *_a, **_k):
        self.errors.append(message)

    def __getattr__(self, _name):
        return lambda *a, **k: None


@pytest.fixture(autouse=True)
def _french_47_0_3(monkeypatch):
    monkeypatch.setattr(reset.time, "sleep", lambda _seconds: None)
    previous = active_locale()
    set_active_locale("fr")
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")
    set_active_locale(previous)


def _search_actions(phone):
    actions = SearchActions.__new__(SearchActions)
    actions.logger = _Log()
    actions.device = phone
    actions.search_selectors = SEARCH_SELECTORS
    return actions


def _rows(screen, username):
    phone = _Phone(screen)
    return [s for s in SEARCH_SELECTORS.user_result_selectors_for_username(username) if phone.xpath(s).exists]


def test_the_profile_left_by_the_direct_run_goes_back_to_the_feed():
    phone = _Phone(HOME, SEARCH_FIELD, RESULTS_TOP, USERS_VERIFIED, PROFILE_LEFT)

    assert return_to_tiktok_home(phone) is True
    assert phone.stack[-1] is HOME


def test_the_absent_handle_has_no_row_among_lookalike_accounts():
    # The tab lists accounts (one of them is found by its own handle), none of them the one asked.
    assert _rows(USERS_ABSENT, "user_4")
    assert _rows(USERS_ABSENT, "user_3") == []


def test_the_verified_account_has_its_row_in_the_users_tab():
    assert _rows(USERS_VERIFIED, "tiktok")


def test_the_verified_account_is_recognised_under_its_badge():
    actions = _search_actions(_Phone(PROFILE_VERIFIED))

    assert actions._landed_on_profile_of("tiktok", settle_timeout=1) is True
    assert actions.logger.errors == []


def test_another_profile_is_still_refused():
    actions = _search_actions(_Phone(PROFILE_VERIFIED))

    assert actions._landed_on_profile_of("tiktok_fan", settle_timeout=1) is False


def _navigation_on(monkeypatch, screen):
    """`navigate_to_user_profile` up to the Users tab, on one screen that stays: the search opened
    and typed (their gestures are not what is read here), each tap landing when its target is on it."""
    from taktik.core.social_media.tiktok.actions.atomic.navigation import search_actions as module

    phone = _Phone(screen)
    actions = _search_actions(phone)
    actions.navigation_selectors = module.NAVIGATION_SELECTORS
    monkeypatch.setattr(module, "return_to_tiktok_shell", lambda *_a, **_k: True)
    actions.open_search = lambda: True
    actions.search_and_submit = lambda _query: True
    actions._human_like_delay = lambda _kind: None
    actions._find_and_click = lambda selectors, timeout=0: any(phone.xpath(s).exists for s in selectors)
    return actions


def test_the_absent_handle_is_said_not_found_on_the_answered_users_tab(monkeypatch):
    """The Users tab lists accounts, none of them this handle: the account is not found."""
    actions = _navigation_on(monkeypatch, USERS_ABSENT)

    assert actions.navigate_to_user_profile("user_3") is False
    assert actions.last_profile_navigation_failure == "not_found"


def test_a_search_that_shows_no_account_row_says_nothing_of_the_account(monkeypatch):
    """No Users tab, no account row (here the feed): a list still loading looks the same, so the
    account is not said absent."""
    actions = _navigation_on(monkeypatch, HOME)

    assert actions.navigate_to_user_profile("user_3") is False
    assert actions.last_profile_navigation_failure == "navigation_failed"


def test_an_opened_profile_leaves_no_failure(monkeypatch):
    actions = _navigation_on(monkeypatch, USERS_VERIFIED)
    actions._landed_on_profile_of = lambda _username, **_k: True

    assert actions.navigate_to_user_profile("tiktok") is True
    assert actions.last_profile_navigation_failure is None
