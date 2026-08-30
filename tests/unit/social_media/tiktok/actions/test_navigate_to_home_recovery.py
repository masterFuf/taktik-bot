"""navigate_to_home must self-heal when the bottom nav bar is hidden.

Device case (hashtag workflow): a failed profile-fetch tap left the app stuck off the
bottom nav (no way to find the Home tab), so every later navigate_to_home/open_search
attempt kept failing and the workflow died with 0 videos. A bounded incremental back
(stop as soon as the "home selected" indicator appears) gives it a way out, mirroring the
same fallback already used on the Instagram side.
"""

from taktik.core.social_media.tiktok.actions.atomic.navigation_actions import NavigationActions


class _Shell:
    """A device whose bottom bar is present or not, and which counts what it was asked.

    A navigation action HAS a device in production, and since 2026-08-30 it uses it before the
    tap: the bar has to exist before a tab can be tapped, so the action backs out of any
    full-screen page first. A double with no device tested a shape nobody runs.
    """

    def __init__(self, bar_after_n_backs: int = 0):
        self.bar_after_n_backs = bar_after_n_backs
        self.shell_backs = 0

    def press(self, _key):
        self.shell_backs += 1

    def xpath(self, _selector):
        present = self.shell_backs >= self.bar_after_n_backs
        return type("Q", (), {"exists": present})()


def _nav(direct_click_ok: bool, home_after_n_backs: int = 0, bar_after_n_backs: int = 0):
    """A NavigationActions whose home_tab click and home-detection are stubbed."""
    nav = object.__new__(NavigationActions)
    nav.device = _Shell(bar_after_n_backs)
    nav.navigation_selectors = type('Selectors', (), {
        'home_tab': ["home_tab_selector"],
        'home_tab_selected': ["home_tab_selected_selector"],
    })()
    nav.logger = type('L', (), {
        'info': lambda *a, **k: None, 'success': lambda *a, **k: None,
        'debug': lambda *a, **k: None, 'warning': lambda *a, **k: None,
    })()
    nav.back_presses = 0

    nav._find_and_click = lambda selectors, timeout=5: direct_click_ok
    nav._human_like_delay = lambda *a, **k: None

    def _press_back():
        nav.back_presses += 1

    nav._press_back = _press_back

    def _element_exists(selectors, timeout=1):
        return nav.back_presses >= home_after_n_backs > 0

    nav._element_exists = _element_exists
    return nav


def test_direct_tap_succeeds_no_fallback_needed():
    nav = _nav(direct_click_ok=True)
    assert nav.navigate_to_home() is True
    assert nav.back_presses == 0


def test_hidden_nav_bar_recovers_via_back():
    # Direct tap fails (nav bar hidden); home appears after 2 back presses.
    nav = _nav(direct_click_ok=False, home_after_n_backs=2)
    assert nav.navigate_to_home() is True
    assert nav.back_presses == 2


def test_gives_up_after_bounded_retries():
    # Never reaches home -> stops after 3 back presses, returns False (no infinite loop).
    nav = _nav(direct_click_ok=False, home_after_n_backs=0)
    assert nav.navigate_to_home() is False
    assert nav.back_presses == 3


def test_the_bar_is_reached_before_the_tab_is_tapped():
    """The fix that came from three separate failures on the same day: a full-screen page hides
    the bottom bar, so the tab tap lands on nothing and the caller reads "the tab is gone"."""
    nav = _nav(direct_click_ok=True, bar_after_n_backs=2)

    assert nav.navigate_to_home() is True
    assert nav.device.shell_backs == 2, "it must back out until the bar is there"


def test_nothing_is_pressed_when_the_bar_is_already_there():
    """A no-op from the feed — which is what makes it safe to do before every tab tap."""
    nav = _nav(direct_click_ok=True, bar_after_n_backs=0)

    assert nav.navigate_to_home() is True
    assert nav.device.shell_backs == 0
