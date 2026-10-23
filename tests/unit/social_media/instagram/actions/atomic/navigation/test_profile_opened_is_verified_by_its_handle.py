"""A profile opened by its handle is verified only when the screen shows that handle.

`_verify_profile_navigation` closes both ways of opening a profile (the search and the deep link,
`navigate_to_profile`). It answered True when it could not read the handle of the profile on
screen: a profile that never loaded (a blank page, the header container and nothing in it, as a
phone without network shows it) counted as the profile asked for, and the workflow went on to read,
like or write to it. A profile shows no handle until it has loaded: the check waits for it, then
answers « not verified » and says so.

The screens are real, anonymized, read through uiautomator2's own engine behind the clone proxy and
the facade the bridges mount:
- Instagram 410.0.0.53.71 in French (Pixel 3): the blank profile of a visit on 2026-09-28
  (`ig410_fr_profile_not_loaded.xml`, the bot's own dump), and a loaded profile whose action bar
  shows `user_1` (`ig410_fr_profile_follow_back.xml`);
- Instagram 447 in French: a loaded profile whose action bar shows `name_1`
  (`ig447_fr_profile_verified_business.xml`).
"""

import pytest
from loguru import logger
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.instagram.actions.atomic.navigation.search_navigation as search_navigation
from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.diagnostics import miss_capture
from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
from taktik.core.social_media.instagram.actions.base.device.facade import DeviceFacade
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
NOT_LOADED_410 = (FIXTURES / "ig410_fr_profile_not_loaded.xml").read_text(encoding="utf-8")
USER_1_410 = (FIXTURES / "ig410_fr_profile_follow_back.xml").read_text(encoding="utf-8")
NAME_1_447 = (FIXTURES / "ig447_fr_profile_verified_business.xml").read_text(encoding="utf-8")


class _Clock:
    """One clock for the waits and the phone: a sleep moves it, a dump takes a quarter second."""

    def __init__(self):
        self.now = 1000.0
        self.start = self.now

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    """Shows each screen of `timeline` from its second on, `[(seconds, xml), ...]`."""

    wait_timeout = 0.0

    def __init__(self, clock, timeline):
        self.clock, self.timeline = clock, timeline
        self.info = {"displayWidth": 1080, "displayHeight": 2160}
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.clock.now += 0.25
        elapsed = self.clock.now - self.clock.start
        return [xml for since, xml in self.timeline if since <= elapsed][-1]

    def app_current(self):
        return {"package": PKG}

    def window_size(self):
        return 1080, 2160


@pytest.fixture
def verify(monkeypatch):
    """`verify(timeline, handle)`: the production check on a phone that plays `timeline`."""
    clock = _Clock()
    monkeypatch.setattr(snapshot_module, "time", clock)
    monkeypatch.setattr(search_navigation, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    monkeypatch.setattr(miss_capture, "blocage_a_signaler", lambda: False)
    set_active_locale("fr")

    def run(timeline, handle):
        nav = NavigationActions(DeviceFacade(CloneAwareDeviceProxy(_Phone(clock, timeline), PKG)))
        return nav._verify_profile_navigation(handle)

    yield run
    set_active_locale(None)


@pytest.fixture
def warnings():
    seen = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    yield seen
    logger.remove(sink)


def test_a_profile_that_never_loads_is_not_verified(verify, warnings):
    assert verify([(0, NOT_LOADED_410)], "user_1") is False
    assert any("not verified" in line and "user_1" in line for line in warnings)


def test_a_profile_that_loads_is_verified_once_its_handle_shows(verify):
    assert verify([(0, NOT_LOADED_410), (2, USER_1_410)], "user_1") is True


def test_the_profile_of_another_account_is_not_verified(verify, warnings):
    assert verify([(0, USER_1_410)], "user_2") is False
    assert any("user_1" in line and "user_2" in line for line in warnings)


def test_a_profile_still_loading_after_the_wait_is_not_verified(verify):
    assert verify([(0, NOT_LOADED_410), (30, USER_1_410)], "user_1") is False


def test_the_handle_shown_on_instagram_447_is_read(verify):
    assert verify([(0, NAME_1_447)], "name_1") is True
    assert verify([(0, NAME_1_447)], "user_1") is False
