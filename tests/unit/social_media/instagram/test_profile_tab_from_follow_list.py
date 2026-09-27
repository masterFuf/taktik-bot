"""navigate_to_profile_tab must get out of a screen that hides the bottom bar.

Device case (Pixel 3, Instagram 410, 2026-09-24): the followers / following lists hide the bottom
bar. Every unfollow run that had read the following list then failed three times on "Cannot click
on profile tab", and its followers sync never ran. The way out is one real Back at a time -- the
shared facade's `press_back()`, not the Instagram facade's `press('back')`, which uiautomator2
ignores.
"""

import taktik.core.social_media.instagram.actions.atomic.detection as detection_module
from taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation import (
    TabNavigationMixin,
)


class _Sel:
    profile_tab = ["profile_tab_selector"]


class _Phone:
    """Screens stacked as Instagram stacks them; only a real Back pops one."""

    def __init__(self, stack):
        self.stack = list(stack)
        self.backs = 0

    def press_back(self):
        self.backs += 1
        if len(self.stack) > 1:
            self.stack.pop()

    def press(self, key):
        # The Instagram facade's press('back'): a name the server ignores
        pass

    @property
    def screen(self):
        return self.stack[-1]


def _nav(phone, monkeypatch):
    class _Detection:
        def __init__(self, _device):
            pass

        def is_on_own_profile(self):
            return phone.screen == "own_profile"

        def is_on_profile_screen(self):
            return phone.screen in ("own_profile", "other_profile")

        def is_followers_list_open(self):
            return phone.screen == "follow_list"

    monkeypatch.setattr(detection_module, "DetectionActions", _Detection)
    nav = object.__new__(TabNavigationMixin)
    nav.device = phone
    nav.selectors = _Sel()
    nav.logger = type("L", (), {"debug": lambda *a, **k: None, "error": lambda *a, **k: None,
                                "warning": lambda *a, **k: None})()
    nav._human_like_delay = lambda *_a, **_k: None
    nav._is_instagram_open = lambda: True
    nav.tab_taps = 0

    def _find_and_click(selectors, timeout=0):
        # The bottom bar exists on the profile and the feed, not on the follow list
        if phone.screen == "follow_list":
            return False
        nav.tab_taps += 1
        phone.stack.append("own_profile")
        return True

    nav._find_and_click = _find_and_click
    phone.dump_hierarchy = lambda: ""
    return nav


def test_from_the_follow_list_it_backs_out_to_the_profile(monkeypatch):
    phone = _Phone(["own_profile", "follow_list"])
    nav = _nav(phone, monkeypatch)

    assert nav.navigate_to_profile_tab() is True
    assert phone.backs == 1


def test_from_another_profile_the_back_is_a_real_one(monkeypatch):
    phone = _Phone(["own_profile", "other_profile"])
    nav = _nav(phone, monkeypatch)

    assert nav.navigate_to_profile_tab() is True
    assert phone.backs == 1
    assert nav.tab_taps == 0


def test_never_backs_out_of_instagram(monkeypatch):
    phone = _Phone(["follow_list"])
    nav = _nav(phone, monkeypatch)
    nav._is_instagram_open = lambda: False

    assert nav.navigate_to_profile_tab() is False
    assert phone.backs == 0


# ── On the real screens: no 15 s search for a tab the follow list hides ─────────────────────

def test_from_the_real_following_list_it_backs_out_without_searching_for_the_tab(monkeypatch):
    """Real dumps of a Pixel 3 (Instagram 410, in French), anonymized: the following list, which
    has no bottom bar (`fixtures/ig410_fr_following_list_sorted_latest.xml`), and the account's
    own profile behind it (`fixtures/ig410_fr_own_profile.xml`). On the phone, the unfollow lost
    15 s here on each return from the list: the tab was searched for before the Back."""
    from pathlib import Path

    from loguru import logger
    from uiautomator2.xpath import XPathEntry

    import taktik.core.shared.actions.base_action as base_action_module
    import taktik.core.shared.device.facade as shared_facade_module
    import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
    from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
    from taktik.core.shared.diagnostics import miss_capture
    from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
    from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
    from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
    from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS

    fixtures = Path(__file__).parent / "fixtures"
    follow_list = (fixtures / "ig410_fr_following_list_sorted_latest.xml").read_text(encoding="utf-8")
    own_profile = (fixtures / "ig410_fr_own_profile.xml").read_text(encoding="utf-8")

    class Clock:
        """What `_find_and_click` waits on: each reading of the time is 0.7 s later."""

        def __init__(self):
            self.now = 0.0

        def time(self):
            self.now += 0.7
            return self.now

        def sleep(self, _seconds):
            pass

    class RealPhone:
        wait_timeout = 1.0
        info = {"displayWidth": 1080, "displayHeight": 2160}

        def __init__(self, screen, back_to):
            self.screen, self.back_to = screen, back_to
            self.presses, self.taps = [], []
            self.xpath = XPathEntry(self)

        def dump_hierarchy(self, *_a, **_k):
            return self.screen

        def app_current(self):
            return {"package": "com.instagram.android"}

        def window_size(self):
            return 1080, 2160

        def press(self, key, meta=None):
            self.presses.append(key)
            if key == "back":
                self.screen = self.back_to
            return True

        def click(self, x, y):
            self.taps.append((x, y))

    clock = Clock()
    for module in (facade_module, shared_facade_module):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr(base_action_module, "time", clock)
    monkeypatch.setattr(miss_capture, "signaler_ecran_inconnu", lambda *a, **k: None)
    set_active_locale("fr")
    try:
        phone = RealPhone(follow_list, back_to=own_profile)
        nav = object.__new__(TabNavigationMixin)
        nav.device = DeviceFacade(CloneAwareDeviceProxy(phone, "com.instagram.android"))
        nav.logger = logger.bind(module="test_profile_tab_from_follow_list")
        nav.selectors = NAVIGATION_SELECTORS
        nav.detection_selectors = DETECTION_SELECTORS
        nav._method_stats = {"clicks": 0, "waits": 0, "sleeps": 0, "errors": 0}
        nav._platform = "instagram"
        nav._human_like_delay = lambda *a, **k: None

        assert nav.navigate_to_profile_tab() is True
    finally:
        set_active_locale(None)

    assert phone.presses == ["back"] and phone.taps == []
    assert clock.now < 15, f"searched {clock.now:.1f} s for a tab the list hides"
