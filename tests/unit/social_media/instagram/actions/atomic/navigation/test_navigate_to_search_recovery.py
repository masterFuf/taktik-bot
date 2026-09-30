"""navigate_to_search must self-heal when the bottom nav bar is hidden.

Device case (hashtag automation): the bot got parked on a fullscreen surface (a reel/clips viewer)
that hides the bottom nav bar, so the search-tab tap found nothing and EVERY hashtag iteration
looped forever on "Cannot navigate to search screen" (0 interactions for minutes). The recovery is
to return to a known state (home) and retry the tab once.
"""

from taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation import (
    TabNavigationMixin,
)


class _Sel:
    search_tab = ["search_tab_selector"]


def _nav(tab_results):
    """A TabNavigationMixin whose _navigate_to_tab yields the given booleans in order."""
    nav = object.__new__(TabNavigationMixin)
    nav.selectors = _Sel()
    nav._is_search_screen = lambda: True
    seq = iter(tab_results)
    nav.tab_calls = 0
    nav.home_calls = 0
    nav.opened = 0

    def _tab(selectors, name, emoji, verify):
        nav.tab_calls += 1
        return next(seq, tab_results[-1])

    nav._navigate_to_tab = _tab
    nav.navigate_to_home = lambda: setattr(nav, 'home_calls', nav.home_calls + 1) or True
    nav._is_instagram_open = lambda: True
    nav._open_instagram = lambda: setattr(nav, 'opened', nav.opened + 1) or True
    nav.logger = type('L', (), {'warning': lambda *a, **k: None, 'debug': lambda *a, **k: None})()
    return nav


def test_happy_path_no_recovery():
    # Search tab found on the first try -> no home reset.
    nav = _nav([True])
    assert nav.navigate_to_search() is True
    assert nav.tab_calls == 1
    assert nav.home_calls == 0


def test_recovers_via_home_when_nav_bar_hidden():
    # First tap fails (fullscreen surface), recover through home, second tap succeeds.
    nav = _nav([False, True])
    assert nav.navigate_to_search() is True
    assert nav.home_calls == 1, "should return to home to restore the nav bar"
    assert nav.tab_calls == 2, "should retry the search tab once after recovering"


def test_brings_instagram_foreground_if_left_the_app():
    nav = _nav([False, True])
    nav._is_instagram_open = lambda: False  # a stray back dropped us to the launcher
    assert nav.navigate_to_search() is True
    assert nav.opened == 1, "should re-open Instagram before retrying"
