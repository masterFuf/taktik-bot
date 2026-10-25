"""After a DM, the cold DM goes home by the production way back, keyboard or not.

Pixel 6a (Instagram 447, French, 2026-10-25), CLI coldDm: the DM sent, `go_home` looked four times
for the home tab (« No element found ») and the run stayed on the results of the search that had
opened the profile. The way home is the production one (`NavigationActions.navigate_to_home`, Backs
one at a time by `_back_out_until`, three screens at most), and it was taken: but the keyboard was
still up over the conversation after Send, and hiding it took the first of the three Backs. The
second left the conversation, the third the profile; the fourth, that would have shown Explore and
its tab bar, never came.

The screens are the four the run kept, one per look for the home tab (`search_screens_phone.py`,
`WAY_HOME_AFTER_A_COLD_DM`), then the Explore grid and the home feed of the same phone, behind the
clone proxy and the facade the bridge mounts.
"""

from contextlib import ExitStack
from types import SimpleNamespace

import pytest

import taktik.core.shared.actions.base_action as base_action_module
import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.base.base_action.delays as delays_module
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.cold_dm.workflow import ColdDMWorkflow
from unit.social_media.instagram.actions.atomic.navigation.search_screens_phone import (
    PKG,
    SEARCH_447,
    WAY_HOME_AFTER_A_COLD_DM,
    RunningClock,
    SearchPhone,
    selectors_of,
)


@pytest.fixture
def way_home(monkeypatch):
    """`way_home(stack)`: the cold DM's `go_home` from the first screen of `stack` (each Back shows
    the next one), and the phone it ran on."""
    for module in (facade_module, shared_facade_module, delays_module):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(base_action_module, "time", RunningClock())
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    set_active_locale("fr")
    versions = ExitStack()

    def run(stack):
        versions.enter_context(selectors_of(SEARCH_447))
        phone = SearchPhone(SEARCH_447, stack=stack)
        proxy = CloneAwareDeviceProxy(phone, PKG)
        arrived = ColdDMWorkflow(DeviceFacade(proxy), SimpleNamespace(device=proxy)).go_home()
        return arrived, phone

    with versions:
        yield run
    set_active_locale(None)


def test_from_the_conversation_typed_in_the_cold_dm_gets_home(way_home):
    """Keyboard, conversation, profile, search results: four Backs, then the home tab of Explore."""
    arrived, phone = way_home(WAY_HOME_AFTER_A_COLD_DM)

    assert arrived is True
    assert phone.screen is SEARCH_447.home
    assert phone.presses == ["back"] * 4


def test_the_keyboard_is_not_one_of_the_three_screens(way_home):
    """Without the keyboard, the same way home is three Backs: the bound is unchanged."""
    arrived, phone = way_home(WAY_HOME_AFTER_A_COLD_DM[1:])

    assert arrived is True
    assert phone.screen is SEARCH_447.home
    assert phone.presses == ["back"] * 3


def test_never_more_than_three_screens_after_the_keyboard(way_home):
    """One screen more under the conversation (no tab bar anywhere): the way back stops after the
    keyboard and three screens, where it is, rather than Back on and on."""
    stack = WAY_HOME_AFTER_A_COLD_DM[:2] + WAY_HOME_AFTER_A_COLD_DM[1:4]
    arrived, phone = way_home(stack)

    assert arrived is False
    assert phone.presses == ["back"] * 4
    assert phone.screen is WAY_HOME_AFTER_A_COLD_DM[3]
