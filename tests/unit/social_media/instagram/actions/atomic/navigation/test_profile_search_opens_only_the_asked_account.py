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

The screens are real (`search_screens_phone.py`): the home feed, Explore, the results, on
Instagram 410 and 447 in French. The keyboard is not what is tested: it types what it is given.
What the profile shows once opened is not either (`_verify_profile_navigation`, recorded here).
"""

import time as real_time

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

from search_screens_phone import PKG, SEARCH_410, SEARCH_447, SearchPhone


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
    """`phone_on(screens)`: the phone, its keyboard typing into it, nothing waited for."""
    deep_links = []

    def build(screens):
        phone = SearchPhone(screens)
        monkeypatch.setattr(base_action_module, "ensure_taktik_keyboard", lambda *_a, **_k: True)
        monkeypatch.setattr(base_action_module, "clear_text_with_taktik_keyboard", lambda *_a, **_k: True)
        monkeypatch.setattr(base_action_module, "type_text_checked",
                            lambda _device, _serial, text, **_k: phone.keyboard_types(text) or True)
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
    yield build
    set_active_locale(None)


def _navigation(phone, opened):
    """The production navigation on the device a bridge hands it; the profile check recorded."""
    nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, PKG)))
    nav._verify_profile_navigation = lambda handle: opened.append(handle) or True
    return nav


@pytest.mark.parametrize("screens, handle", [(SEARCH_410, "user_2"), (SEARCH_447, "user_2")],
                         ids=["ig410", "ig447"])
def test_the_account_listed_is_opened_by_its_row(phone_on, screens, handle):
    phone, opened = phone_on(screens), []

    assert _navigation(phone, opened).navigate_to_profile(handle, force_search=True) is True

    assert phone.typed == [handle]
    assert phone.rows_tapped() == [handle]
    assert opened == [handle]


def test_an_account_listed_only_in_a_keyword_row_opens_nobody(phone_on):
    """Instagram 447: `user_3` typed, `user_3x` the first account row. Nobody is opened, and with
    `force_search` no deep link either."""
    phone, opened = phone_on(SEARCH_447), []

    assert _navigation(phone, opened).navigate_to_profile("user_3", force_search=True) is False

    assert phone.typed == ["user_3"]
    assert phone.rows_tapped() == []
    assert opened == [] and phone.deep_links == []


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
