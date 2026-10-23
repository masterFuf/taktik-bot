"""The Lab's `navigation.open_profile` can test the profile search alone (`forceSearch`).

Without it, the action ends on the deep link when the search finds nothing: on Instagram 447,
"nasa" opened by the deep link and hid that the search had listed no row of it. With `forceSearch`
the action asks the production search what the cold DM asks it (`force_search=True`): the search
or nobody. Its yes/no is read by the Lab's one reading of a yes/no (`lab_flag`).

The screens are the real ones of the production search's tests (`search_screens_phone.py`):
Instagram 447 in French, `user_3` listed only in a keyword row.
"""

import time as real_time
from types import SimpleNamespace

import pytest

import taktik.core.shared.actions.base_action as base_action_module
import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation as search_navigation
import taktik.core.social_media.instagram.actions.base.base_action.delays as delays_module
import taktik.core.social_media.instagram.actions.base.device.facade as facade_module
from bridges.tools.lab.actions.instagram.navigation import open_profile
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.atomic.navigation.deep_link_navigation import (
    DeepLinkNavigationMixin,
)
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.social_media.instagram.actions.atomic.navigation.search_screens_phone import (
    PKG,
    SEARCH_447,
    SearchPhone,
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
def lab(monkeypatch):
    """`lab(params)`: the Lab action on the 447 search screens, and the deep links it tried."""
    for module in (facade_module, shared_facade_module, search_navigation, delays_module):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(base_action_module, "time", _Clock())
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    monkeypatch.setattr(search_navigation, "get_active_package", lambda: PKG)
    monkeypatch.setattr(base_action_module, "ensure_taktik_keyboard", lambda *_a, **_k: True)
    monkeypatch.setattr(base_action_module, "clear_text_with_taktik_keyboard", lambda *_a, **_k: True)
    deep_links = []
    monkeypatch.setattr(DeepLinkNavigationMixin, "_navigate_via_deep_link",
                        lambda _self, username, *a, **k: deep_links.append(username) or False)
    set_active_locale("fr")

    def run(params):
        phone = SearchPhone(SEARCH_447)
        monkeypatch.setattr(base_action_module, "type_text_checked",
                            lambda _device, _serial, text, **_k: phone.keyboard_types(text) or True)
        bundle = SimpleNamespace(nav=NavigationActions(DeviceFacade(CloneAwareDeviceProxy(phone, PKG))))
        return SimpleNamespace(result=open_profile(bundle, params), phone=phone, deep_links=deep_links)

    yield run
    set_active_locale(None)


@pytest.mark.parametrize("force", [True, "true", "oui", "1"])
def test_force_search_tests_the_search_alone(lab, force):
    run = lab({"username": "user_3", "forceSearch": force})

    assert run.result is False
    assert run.phone.typed == ["user_3"] and run.phone.rows_tapped() == []
    assert run.deep_links == []


@pytest.mark.parametrize("params", [{"username": "user_3"}, {"username": "user_3", "forceSearch": "false"}],
                         ids=["absent", "false"])
def test_without_it_the_deep_link_follows_a_search_that_found_nothing(lab, params):
    assert lab(params).deep_links == ["user_3"]


def test_a_force_search_that_says_neither_yes_nor_no_is_refused(lab):
    with pytest.raises(ValueError, match="forceSearch"):
        lab({"username": "user_3", "forceSearch": "maybe"})
