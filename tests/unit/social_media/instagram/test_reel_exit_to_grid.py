"""A reel must be exited to the grid, never scrolled in-viewer.

Device case (like posts on a profile): opening a REEL from the grid drops the bot in the full-screen
clips viewer. Advancing in-viewer scrolls the REELS FEED (not the profile's posts), and after the
first reel the top-left Back button disappears — trapping the run in an endless reels feed with no
way out (bot stuck, every later workflow failed to navigate to search). The fix: for a reel, exit to
the grid (Back still present on the freshly opened reel) and open another post instead of scrolling.
"""

from taktik.core.social_media.instagram.actions.business.actions.like.post_navigation import (
    PostNavigationMixin,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import POST_SELECTORS
import taktik.core.social_media.instagram.actions.business.actions.like.post_navigation as post_nav

_CLIPS_BACK = '//*[@resource-id="com.instagram.android:id/clips_action_bar_start_action_buttons"]//android.widget.ImageView'


def _nav():
    nav = object.__new__(PostNavigationMixin)
    nav.calls = []
    nav._return_to_grid_and_open_another_post = lambda total=0, username=None: (nav.calls.append('grid') or True)
    nav._navigate_to_next_post_in_sequence = lambda: (nav.calls.append('scroll') or True)
    return nav


def test_reel_exits_to_grid_not_inviewer_scroll():
    nav = _nav()
    nav._advance_or_exit_reel(is_reel=True, total_posts_on_profile=12, username='x')
    assert nav.calls == ['grid'], "a reel must exit to the grid, never scroll the reels feed"


def test_normal_post_advances_in_viewer():
    nav = _nav()
    nav._advance_or_exit_reel(is_reel=False, total_posts_on_profile=12, username='x')
    assert nav.calls == ['scroll'], "a normal post advances in-viewer as before"


def test_reel_exit_propagates_failure():
    nav = _nav()
    nav._return_to_grid_and_open_another_post = lambda total=0, username=None: False
    assert nav._advance_or_exit_reel(is_reel=True) is False, "caller must be able to stop when exit fails"


def test_post_back_selectors_include_the_clips_back_button():
    # The clips/reels viewer Back lives in the clips action bar, not action_bar_button_back;
    # without this selector _return_to_profile_from_post can't leave a reel and falls back to a
    # swipe that doesn't exit the viewer.
    assert _CLIPS_BACK in POST_SELECTORS.back_button_selectors


def test_failed_downward_dismiss_falls_back_to_back_not_opposite_swipe(monkeypatch):
    calls = []

    class _XPath:
        exists = False

    class _Device:
        @staticmethod
        def xpath(_selector):
            return _XPath()

        @staticmethod
        def get_screen_size():
            return 1080, 2280

        @staticmethod
        def press(key):
            calls.append(("press", key))

    class _Scroll:
        @staticmethod
        def _plan_behavior_gesture(_context, _gesture):
            return {
                "distance_scale": 1.0,
                "velocity_scale": 1.0,
                "settle_scale": 1.0,
            }

        @staticmethod
        def _human_swipe(**kwargs):
            calls.append(("swipe", kwargs))
            return False

    nav = object.__new__(PostNavigationMixin)
    nav.device = _Device()
    nav.scroll_actions = _Scroll()
    nav.post_selectors = POST_SELECTORS
    nav.logger = type("_Log", (), {
        "info": lambda *_a, **_k: None,
        "debug": lambda *_a, **_k: None,
        "error": lambda *_a, **_k: None,
    })()
    monkeypatch.setattr(post_nav.time, "sleep", lambda _seconds: None)

    returned = nav._return_to_profile_from_post()

    assert returned is True
    assert calls[0][0] == "swipe"
    assert calls[0][1]["direction"] == "down"
    assert calls[1] == ("press", "back")


def test_injected_but_ignored_dismiss_falls_back_to_back_after_ui_check(monkeypatch):
    calls = []

    class _XPath:
        exists = False

    class _Device:
        @staticmethod
        def xpath(_selector):
            return _XPath()

        @staticmethod
        def get_screen_size():
            return 1080, 2280

        @staticmethod
        def press(key):
            calls.append(("press", key))

    class _Scroll:
        @staticmethod
        def _plan_behavior_gesture(_context, _gesture):
            return {
                "distance_scale": 1.0,
                "velocity_scale": 1.0,
                "settle_scale": 1.0,
            }

        @staticmethod
        def _human_swipe(**kwargs):
            calls.append(("swipe", kwargs))
            return True

    checks = iter([True] * 8 + [False])
    nav = object.__new__(PostNavigationMixin)
    nav.device = _Device()
    nav.scroll_actions = _Scroll()
    nav.post_selectors = POST_SELECTORS
    nav._is_in_post_view = lambda: next(checks)
    nav.logger = type("_Log", (), {
        "info": lambda *_a, **_k: None,
        "debug": lambda *_a, **_k: None,
        "error": lambda *_a, **_k: None,
    })()
    monkeypatch.setattr(post_nav.time, "sleep", lambda _seconds: None)

    assert nav._return_to_profile_from_post() is True
    assert calls[0][0] == "swipe"
    assert calls[1] == ("press", "back")
