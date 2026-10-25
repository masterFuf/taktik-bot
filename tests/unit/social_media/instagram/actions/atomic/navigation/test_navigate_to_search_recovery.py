"""navigate_to_search must self-heal when the bottom nav bar is hidden.

Device case (hashtag automation): the bot got parked on a fullscreen surface (a reel/clips viewer)
that hides the bottom nav bar, so the search-tab tap found nothing and EVERY hashtag iteration
looped forever on "Cannot navigate to search screen" (0 interactions for minutes). The recovery
backs out one screen at a time and stops on the first one that is the search screen or shows the
tab bar. It used to go home first (three Backs) and retry the tab once: on Instagram 447 that ended
on search results without the tab bar, which nothing recognised (the real screens of that case:
`test_profile_search_opens_only_the_asked_account.py`).

The sequencing alone is tested here, on a stand-in for the screen: what each Back reaches.
"""

from taktik.core.social_media.instagram.actions.atomic.navigation.tab_navigation import (
    TabNavigationMixin,
)


class _Sel:
    search_tab = ["search_tab_selector"]


def _nav(tab_results, search_bar=(False,)):
    """A TabNavigationMixin whose search-tab taps and search-bar checks yield the given booleans
    in order (the last one repeated), and whose Backs are counted."""
    nav = object.__new__(TabNavigationMixin)
    nav.selectors = _Sel()
    nav._is_search_screen = lambda: True
    taps, bars = iter(tab_results), iter(search_bar)
    nav.tab_calls = nav.backs = nav.opened = nav.home_calls = 0

    def _tab(selectors, name, emoji, verify):
        nav.tab_calls += 1
        return next(taps, tab_results[-1])

    nav._navigate_to_tab = _tab
    nav._is_search_bar_shown = lambda: next(bars, search_bar[-1])
    nav._is_element_present = lambda selectors: False  # no keyboard up
    nav._back_one_screen = lambda: setattr(nav, "backs", nav.backs + 1)
    nav.navigate_to_home = lambda: setattr(nav, "home_calls", nav.home_calls + 1) or True
    nav._is_instagram_open = lambda: True
    nav._open_instagram = lambda: setattr(nav, "opened", nav.opened + 1) or True
    nav.logger = type("L", (), {"warning": lambda *a, **k: None, "debug": lambda *a, **k: None})()
    return nav


def test_happy_path_no_recovery():
    # Search tab found on the first try -> no Back.
    nav = _nav([True])
    assert nav.navigate_to_search() is True
    assert nav.tab_calls == 1
    assert nav.backs == 0


def test_the_search_screen_already_up_is_used_as_it_is():
    nav = _nav([False], search_bar=(True,))
    assert nav.navigate_to_search() is True
    assert nav.tab_calls == 0 and nav.backs == 0


def test_recovers_by_a_back_that_brings_the_tab_bar():
    # First tap fails (fullscreen surface), one Back, the tab is there.
    nav = _nav([False, True])
    assert nav.navigate_to_search() is True
    assert nav.backs == 1
    assert nav.tab_calls == 2
    assert nav.home_calls == 0, "never home first: the search screen may be on the way"


def test_stops_on_the_search_screen_reached_by_a_back():
    # No tab bar anywhere; the third Back shows the search screen.
    nav = _nav([False], search_bar=(False, False, False, True))
    assert nav.navigate_to_search() is True
    assert nav.backs == 3


def test_it_never_backs_more_than_three_screens():
    nav = _nav([False])
    assert nav.navigate_to_search() is False
    assert nav.backs == 3


def test_brings_instagram_foreground_if_left_the_app():
    nav = _nav([False, True])
    nav._is_instagram_open = lambda: False  # a stray back dropped us to the launcher
    assert nav.navigate_to_search() is True
    assert nav.opened == 1, "should re-open Instagram before retrying"
    assert nav.backs == 0
