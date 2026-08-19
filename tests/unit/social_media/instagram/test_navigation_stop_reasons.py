"""End-of-list detection must keep emitting the exact sentences it emitted before.

`_handle_scroll_and_end_detection` decides why a followers run ran dry, and it had no test at
all. Routing its six motives through the catalogue meant re-passing their arguments by hand --
`known_streak(streak, seen)` reads the same as `known_streak(seen, streak)` and produces a
sentence the desktop app would no longer recognise, silently.

So the real method is driven into each of its six outcomes and the sentence is compared to the
one it produced before. The structured code is checked alongside, which is what the app will
read once it stops matching sentences.
"""

import types

from taktik.core.social_media.instagram.actions.business.workflows.followers.workflows.direct.navigation_helpers import (
    DirectNavigationMixin,
)


def _detector(is_end=False, load_more=False):
    return types.SimpleNamespace(
        is_the_end=lambda: is_end,
        click_load_more_if_present=lambda: load_more,
    )


def _tracker(end_of_list=False):
    return types.SimpleNamespace(is_end_of_list=lambda: end_of_list)


def _nav(load_more_result=None):
    """The mixin with only what this method touches."""
    nav = object.__new__(DirectNavigationMixin)
    nav.logger = types.SimpleNamespace(
        info=lambda *a, **k: None, debug=lambda *a, **k: None,
        warning=lambda *a, **k: None, error=lambda *a, **k: None,
    )
    nav.scroll_actions = types.SimpleNamespace(
        check_and_click_load_more=lambda: load_more_result
    )
    nav._human_like_delay = lambda *a, **k: None
    return nav


def _detect(nav, *, seen=0, target=0, no_new=0, known_streak=0,
            max_known=None, max_scrolls=None, detector=None, tracker=None):
    return nav._handle_scroll_and_end_detection(
        0,                      # new_usernames_found -- zero, or nothing is detected
        no_new,                 # no_new_profiles_count
        seen,                   # total_usernames_seen
        target,                 # target_followers_count
        detector or _detector(),
        tracker or _tracker(),
        0,                      # scroll_attempts
        0,                      # new_profiles_to_interact
        False,                  # did_interact_this_iteration
        {},                     # stats
        100,                    # max_interactions
        known_streak,
        max_known,
        max_scrolls,
    )


def test_known_username_streak_keeps_its_sentence():
    stop, reason = _detect(_nav(), seen=472, known_streak=150, max_known=150)

    assert stop is True
    assert reason == "No new followers after 150 known usernames in a row (472 seen)"
    assert reason.code == "known_streak"
    assert reason.params == {"streak": 150, "seen": 472}


def test_reaching_the_end_of_the_list_keeps_its_sentence():
    # 95% of the target count is the threshold, and both numbers group thousands.
    stop, reason = _detect(_nav(), seen=5000, target=5100)

    assert stop is True
    assert reason == "End of followers list (5,000/5,100 seen)"
    assert reason.code == "end_of_list"


def test_the_scroll_detector_verdict_keeps_its_sentence():
    stop, reason = _detect(_nav(), seen=472, detector=_detector(is_end=True))

    assert stop is True
    assert reason == "No new followers found (472 profiles seen)"
    assert reason.code == "no_new_profiles"


def test_repeated_profiles_keep_their_sentence():
    stop, reason = _detect(_nav(), seen=472, tracker=_tracker(end_of_list=True))

    assert stop is True
    assert reason == "End of followers list (same profiles repeated)"
    assert reason.code == "end_of_list_repeated"


def test_the_scroll_attempt_streak_keeps_its_sentence():
    stop, reason = _detect(_nav(), seen=472, no_new=10, max_scrolls=10)

    assert stop is True
    assert reason == "No new followers after 10 scroll attempts (472 seen)"
    assert reason.code == "scroll_streak"
    assert reason.params == {"scrolls": 10, "seen": 472}


def test_the_suggestions_section_keeps_its_sentence():
    # A "load more" button that reports False means Instagram switched to suggested accounts.
    stop, reason = _detect(_nav(load_more_result=False), seen=472)

    assert stop is True
    assert reason == "End of followers list (suggestions section)"
    assert reason.code == "end_of_list_suggestions"


def test_nothing_is_reported_while_the_list_still_yields():
    stop, reason = _detect(_nav(), seen=100, target=5000)

    assert stop is False
    assert reason is None
