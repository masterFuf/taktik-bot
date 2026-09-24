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
