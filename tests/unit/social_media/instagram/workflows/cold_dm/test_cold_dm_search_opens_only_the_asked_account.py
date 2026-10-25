"""The cold DM opens its recipient through the production profile search: that exact account, or nobody.

Instagram 447 (Pixel 6a, in French, 2026-09-28) no longer lists some accounts among the accounts its
search shows: typed "nasa", the screen held a "keyword" row whose subtitle names the account ("nasa •
104 M followers"), and account rows for others, the first of them @nasahubble. The cold DM had a
search of its own, which took the first account row whose handle held the query: it opened
@nasahubble, and the DM would have gone to someone else. Fixed there first, it was still a second
way of opening a profile by its handle. The cold DM now asks the production one
(`NavigationActions.navigate_to_profile`, every workflow's), with `force_search`: never a deep link,
as the cold DM always reached its recipients. The rules its own search held (the exact handle,
read as Instagram writes it) are that search's, tested on its own screens in
`actions/atomic/navigation/test_profile_search_opens_only_the_asked_account.py`. That search
now also opens an account Instagram 447 lists only in a keyword row (subtitle "nasa • 104 M
followers"), by the account row of that keyword's results: the cold DM reaches it there, by the
same production path.

The screens are those real captures (`search_screens_phone.py`: the home feed, Explore, the results),
behind the clone proxy and the facade the bridge mounts. The keyboard is not what is tested: it
types what it is given. Neither is the profile opened: once the row is tapped, the check of the
opened profile and the cold DM's decision on it are recorded, not played.
"""

from contextlib import ExitStack
from types import SimpleNamespace

import pytest

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
from taktik.core.social_media.instagram.workflows.cold_dm.navigation import NOT_ON_PROFILE
from taktik.core.social_media.instagram.workflows.cold_dm.workflow import NOT_FOUND, ColdDMWorkflow
from unit.social_media.instagram.actions.atomic.navigation.search_screens_phone import (
    PKG,
    SEARCH_410,
    SEARCH_447,
    RunningClock,
    SEARCH_447_KEYWORD_ROW,
    SearchPhone,
    selectors_of,
)


@pytest.fixture
def run_on(monkeypatch):
    """`run_on(screens, recipient)`: one recipient through `reach_and_send` on that phone, and
    what happened: the phone, the outcome, the profile checks and decisions, the deep links."""
    for module in (facade_module, shared_facade_module, search_navigation, delays_module):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(base_action_module, "time", RunningClock())
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    monkeypatch.setattr(search_navigation, "get_active_package", lambda: PKG)
    monkeypatch.setattr(base_action_module, "ensure_taktik_keyboard", lambda *_a, **_k: True)
    monkeypatch.setattr(base_action_module, "clear_text_with_taktik_keyboard", lambda *_a, **_k: True)
    seen = SimpleNamespace(checked=[], decided=[], deep_links=[], composed=[])
    monkeypatch.setattr(DeepLinkNavigationMixin, "_navigate_via_deep_link",
                        lambda _self, username, *a, **k: seen.deep_links.append(username) or False)
    monkeypatch.setattr(NavigationActions, "_verify_profile_navigation",
                        lambda _self, handle: seen.checked.append(handle) or True)
    monkeypatch.setattr(ColdDMWorkflow, "open_dm_from_profile",
                        lambda _self, policy=None, recipient=None: seen.decided.append(policy) or NOT_ON_PROFILE)
    set_active_locale("fr")
    versions = ExitStack()

    def run(screens, recipient):
        versions.enter_context(selectors_of(screens))
        phone = SearchPhone(screens)
        monkeypatch.setattr(base_action_module, "type_text_checked",
                            lambda _device, _serial, text, **_k: phone.keyboard_types(text) or True)
        proxy = CloneAwareDeviceProxy(phone, PKG)
        workflow = ColdDMWorkflow(DeviceFacade(proxy), SimpleNamespace(device=proxy))
        seen.phone = phone
        seen.reached = workflow.reach_and_send(recipient, lambda: seen.composed.append(1) or "Bonjour")
        return seen

    with versions:
        yield run
    set_active_locale(None)


def test_an_account_the_results_list_only_in_a_keyword_row_is_reached_through_that_row(run_on):
    seen = run_on(SEARCH_447_KEYWORD_ROW, "name_1")

    assert seen.phone.typed == ["name_1"]
    assert seen.phone.keyword_rows_tapped() == ["name_1"]
    assert seen.phone.rows_tapped() == ["name_1", "name_1"]
    assert seen.checked == ["name_1"]
    assert len(seen.decided) == 1 and seen.reached == {"outcome": NOT_ON_PROFILE}
    assert seen.deep_links == [] and seen.composed == []


def test_an_account_the_results_do_not_list_opens_nobody(run_on):
    """`user_3x` is listed (an account row), `user_3` too (a keyword row); `user_3y` is not."""
    seen = run_on(SEARCH_447, "user_3y")

    assert seen.reached == {"outcome": NOT_FOUND}
    assert seen.phone.typed == ["user_3y"]
    # The search bar is tapped to type; no row is, and no deep link reaches the profile instead.
    assert seen.phone.rows_tapped() == []
    assert seen.deep_links == [] and seen.checked == [] and seen.decided == [] and seen.composed == []


@pytest.mark.parametrize("screens", [SEARCH_410, SEARCH_447], ids=["ig410", "ig447"])
def test_the_recipient_is_opened_by_the_row_of_its_handle(run_on, screens):
    """Given as an operator may type it: the production search reads it as Instagram writes it."""
    seen = run_on(screens, "@User_2")

    assert seen.phone.typed == ["user_2"]
    assert seen.phone.rows_tapped() == ["user_2"]
    assert seen.checked == ["user_2"]
    # Then the cold DM decides on the profile, as before.
    assert len(seen.decided) == 1 and seen.reached == {"outcome": NOT_ON_PROFILE}
    assert seen.deep_links == [] and seen.composed == []
