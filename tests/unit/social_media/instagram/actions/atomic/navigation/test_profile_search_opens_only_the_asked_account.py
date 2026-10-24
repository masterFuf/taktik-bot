"""The production profile search opens the account it was asked for, or nobody.

It is the one search of a profile by its handle (`NavigationActions.navigate_to_profile`), for
every workflow that opens a profile, the cold DM among them. The cold DM's former search of its own
held two rules, which are this search's:
- the row opened is the row of the exact handle, never one whose handle merely holds the query: on
  Instagram 447 an account the results list only in a keyword row left the first account row
  around it, someone else's (`@nasahubble` for "nasa");
- the handle is read as Instagram writes it: spaces and a leading `@` dropped, lower case. The
  cold DM lowered its handle; this search typed and looked for the text as given, so `@Nasa` or
  ` nasa` matched no row and opened nobody.
A text that is no Instagram handle once read that way is refused before any gesture: it was
typed, then written into the XPath of the rows (a `"` broke it).

Instagram 447 lists some accounts only in a keyword row: a title that is a query, a subtitle that
names the account ("nasa • 104 M followers"). The search read only the account rows and opened
nobody there (the phone session of 2026-10-24: `forceSearch` on @nasa, False; the deep link hid
it). It now taps the keyword row whose subtitle starts with the exact handle and its " •" (a 447
version override), never a neighbour's ("nasasolarsystem • 2,7 M followers"). That tap opens no
profile (replayed on the phone the same day): it opens the results of the keyword, whose first row
is the account row of the handle; the search then taps that account row, by its username, the one
proof of the handle. No tap reaches a button drawn over a row: the avatar ring (a story), the
follow button of the keyword's results.

The search also starts from where an earlier run left the phone (same session, a cold DM after a
likers run): a likers sheet over a post, the post, the profile it was opened from, then the
results of the search that opened that profile, none of them with the tab bar on 447. The search
went "home" by three Backs, stopped on those results without knowing them, and found no tab:
"Cannot access search screen", nothing sent. The search screen is now the screen of its own bar
(`search_screen_bar`): used as it is when it is up, and the way back stops on it.

The screens are real (`search_screens_phone.py`): the home feed, Explore, the results, on
Instagram 410 and 447 in French, with the selectors their version gets at connect. The keyboard is
not what is tested: it types what it is given. What the profile shows once opened is not either
(`_verify_profile_navigation`, recorded here).
"""

import time as real_time
from contextlib import ExitStack

import pytest
from loguru import logger

import taktik.core.shared.actions.base_action as base_action_module
import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation as search_navigation
import taktik.core.social_media.instagram.actions.base.base_action.delays as delays_module
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.navigation.deep_link_navigation import (
    DeepLinkNavigationMixin,
)
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

from search_screens_phone import (
    PKG,
    SEARCH_410,
    LEFT_OPEN_STACK,
    SEARCH_447,
    SEARCH_447_KEYWORD_ROW,
    SEARCH_447_LEFT_OPEN,
    SearchPhone,
    row_buttons,
    selectors_of,
)


class _Clock:
    """The waits loop on `time.time()`: a clock that runs, and sleeps that do not."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        self.now += 0.7
        return self.now

    def sleep(self, _seconds):
        pass

    def __getattr__(self, name):
        return getattr(real_time, name)


@pytest.fixture
def phone_on(monkeypatch):
    """`phone_on(screens, stack)`: the phone (on the first screen of `stack` when given), its
    keyboard typing into it, nothing waited for, the selectors of its version; the zones its taps
    were aimed at in `phone.tap_zones`."""
    deep_links = []
    versions = ExitStack()
    aimed_human_tap = shared_facade_module.BaseDeviceFacade.human_tap

    def build(screens, stack=()):
        phone = SearchPhone(screens, stack=stack)
        phone.tap_zones = []
        versions.enter_context(selectors_of(screens))
        monkeypatch.setattr(base_action_module, "ensure_taktik_keyboard", lambda *_a, **_k: True)
        monkeypatch.setattr(base_action_module, "clear_text_with_taktik_keyboard", lambda *_a, **_k: True)
        monkeypatch.setattr(base_action_module, "type_text_checked",
                            lambda _device, _serial, text, **_k: phone.keyboard_types(text) or True)

        def human_tap(facade, bounds, **kwargs):
            phone.tap_zones.append((phone.screen, tuple(bounds)))
            return aimed_human_tap(facade, bounds, **kwargs)

        monkeypatch.setattr(shared_facade_module.BaseDeviceFacade, "human_tap", human_tap)
        phone.deep_links = deep_links
        return phone

    for module in (facade_module, shared_facade_module, search_navigation, delays_module):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(base_action_module, "time", _Clock())
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    monkeypatch.setattr(search_navigation, "get_active_package", lambda: PKG)
    monkeypatch.setattr(DeepLinkNavigationMixin, "_navigate_via_deep_link",
                        lambda _self, username, *a, **k: deep_links.append(username) or False)
    set_active_locale("fr")
    with versions:
        yield build
    set_active_locale(None)


def _navigation(phone, opened):
    """The production navigation on the device a bridge hands it; the profile check recorded."""
    nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    nav._verify_profile_navigation = lambda handle: opened.append(handle) or True
    return nav


def _crosses(zone, box) -> bool:
    return not (box[2] <= zone[0] or box[0] >= zone[2] or box[3] <= zone[1] or box[1] >= zone[3])


@pytest.mark.parametrize("screens, handle", [(SEARCH_410, "user_2"), (SEARCH_447, "user_2")],
                         ids=["ig410", "ig447"])
def test_the_account_listed_is_opened_by_its_row(phone_on, screens, handle):
    phone, opened = phone_on(screens), []

    assert _navigation(phone, opened).navigate_to_profile(handle, force_search=True) is True

    assert phone.typed == [handle]
    assert phone.rows_tapped() == [handle]
    assert opened == [handle]


def test_an_account_listed_only_in_a_keyword_row_is_opened_from_that_keyword_s_results(phone_on):
    """Instagram 447: no account row of `name_1`, the first account row a neighbour's (`name_11`).
    Its keyword row is tapped; on the keyword's results, its account row; no deep link."""
    phone, opened = phone_on(SEARCH_447_KEYWORD_ROW), []

    assert _navigation(phone, opened).navigate_to_profile("name_1", force_search=True) is True

    assert phone.typed == ["name_1"]
    assert phone.keyword_rows_tapped() == ["name_1"]
    assert phone.rows_tapped() == ["name_1", "name_1"]
    assert opened == ["name_1"] and phone.deep_links == []


def test_a_keyword_row_whose_results_list_no_account_row_of_the_handle_opens_nobody(phone_on):
    """`name_1s` holds `name_1` at its start: its own keyword row is tapped, never the first one.
    What it opens was not captured, the screen stays: no account row of `name_1s`, nobody opened."""
    phone, opened = phone_on(SEARCH_447_KEYWORD_ROW), []

    assert _navigation(phone, opened).navigate_to_profile("name_1s", force_search=True) is False

    assert phone.keyword_rows_tapped() == ["name_1s"]
    assert opened == [] and phone.deep_links == []


@pytest.mark.parametrize("handle", ["name_1x", "name_"])
def test_a_handle_no_row_names_opens_nobody(phone_on, handle):
    """`name_1` and its neighbours are listed, not these: no row is tapped, and with
    `force_search` no deep link either."""
    phone, opened = phone_on(SEARCH_447_KEYWORD_ROW), []

    assert _navigation(phone, opened).navigate_to_profile(handle, force_search=True) is False

    assert phone.typed == [handle]
    assert phone.rows_tapped() == []
    assert opened == [] and phone.deep_links == []


@pytest.mark.parametrize("screens, handle", [(SEARCH_447_KEYWORD_ROW, "name_1"), (SEARCH_447, "user_2")],
                         ids=["keyword-row-then-its-results", "account-row"])
def test_the_taps_on_rows_are_aimed_clear_of_the_buttons_over_them(phone_on, screens, handle):
    """The avatar ring (right of a keyword row, left of an account row) opens a story; the follow
    button of an account row of a keyword's results follows: each zone a tap is drawn in leaves
    the buttons of its screen out."""
    phone, opened = phone_on(screens), []

    assert _navigation(phone, opened).navigate_to_profile(handle, force_search=True) is True

    row_zones = phone.tap_zones[-2:] if screens is SEARCH_447_KEYWORD_ROW else phone.tap_zones[-1:]
    assert all(not any(_crosses(zone, button) for button in row_buttons(screen)) for screen, zone in row_zones)
    assert phone.row_buttons_tapped() == []


@pytest.mark.parametrize("screens", [SEARCH_410, SEARCH_447], ids=["ig410", "ig447"])
@pytest.mark.parametrize("given", ["@user_2", " User_2 ", "@USER_2"])
def test_the_handle_is_read_as_instagram_writes_it(phone_on, screens, given):
    phone, opened = phone_on(screens), []

    assert _navigation(phone, opened).navigate_to_profile(given, force_search=True) is True

    assert phone.typed == ["user_2"]
    assert phone.rows_tapped() == ["user_2"]
    assert opened == ["user_2"]


@pytest.mark.parametrize("given", ['user_2" or "1"="1', "user 2", "", None, "a" * 31])
def test_a_text_that_is_no_handle_touches_nothing(phone_on, given):
    phone, opened = phone_on(SEARCH_447), []

    assert _navigation(phone, opened).navigate_to_profile(given) is False

    assert phone.taps == [] and phone.typed == [] and phone.deep_links == []
    assert opened == []


def test_the_search_results_left_open_are_searched_in_as_they_are(phone_on):
    """The capture the phone session kept of the screen the cold DM could not leave; `name_70` is an
    account row of it (the results stay those of the query left open: the phone types, the screen
    does not change)."""
    phone, opened = phone_on(SEARCH_447_LEFT_OPEN, LEFT_OPEN_STACK[-1:]), []

    assert _navigation(phone, opened).navigate_to_profile("name_70", force_search=True) is True

    assert phone.presses == []
    assert phone.typed == ["name_70"]
    assert phone.rows_tapped() == ["name_70"]
    assert opened == ["name_70"] and phone.deep_links == []


def test_from_a_likers_sheet_the_way_back_stops_on_the_search_screen(phone_on):
    """Sheet, post, profile: three Backs, then the search results, where the search goes on."""
    phone, opened = phone_on(SEARCH_447_LEFT_OPEN, LEFT_OPEN_STACK), []

    assert _navigation(phone, opened).navigate_to_profile("name_70", force_search=True) is True

    assert phone.presses == ["back", "back", "back"]
    assert phone.typed == ["name_70"]
    assert phone.rows_tapped() == ["name_70"]
    assert opened == ["name_70"] and phone.deep_links == []
