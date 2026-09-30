"""The likers loop must not scroll into the void when it's NOT on the likers popup.

Device case (hashtag → reel): tapping a reel's like count dropped the bot into the full-screen
clips/Reels viewer instead of the likers list, so get_visible_followers returned 0 and the loop
scrolled ~50 times (~40s) doing nothing. It must detect the wrong screen and leave the post fast.
"""

import logging

from taktik.core.social_media.instagram.workflows.common.likers_base import (
    LikersWorkflowBase,
)


class _DA:
    def get_visible_followers_with_elements(self):
        return []  # always empty (stuck on a wrong screen or end of list)


def _wf(popup_open: bool):
    wf = object.__new__(LikersWorkflowBase)
    wf.session_manager = None
    wf.automation = None
    wf.logger = logging.getLogger("test_likers")
    wf.detection_actions = _DA()
    wf._is_likers_popup_open = lambda: popup_open
    wf.scrolls = 0
    wf.exited = 0

    def _scroll():
        wf.scrolls += 1
        return True

    wf._scroll_likers_popup_up = _scroll
    wf._human_like_delay = lambda *a, **k: None
    wf._exit_wrong_likers_screen = lambda: setattr(wf, 'exited', wf.exited + 1)
    return wf


def _run(wf):
    stats = {'users_interacted': 0, 'users_found': 0}
    wf._interact_with_likers_list(stats, {}, max_interactions=5, source_type='HASHTAG', source_name='#x')


def test_wrong_screen_breaks_fast_and_recovers():
    # Likers popup never opens (we're on the reel/clips viewer).
    wf = _wf(popup_open=False)
    _run(wf)
    assert wf.exited == 1, "should back out of the wrong screen"
    assert wf.scrolls <= 2, f"should not scroll into the void (got {wf.scrolls}, was up to 50)"


def test_open_popup_but_no_more_likers_ends_after_a_few_scrolls():
    # Popup IS open but genuinely no more likers -> end of list after a few scrolls, no recovery.
    wf = _wf(popup_open=True)
    _run(wf)
    assert wf.exited == 0
    assert wf.scrolls <= 4, f"should stop near end of list, not scroll 50x (got {wf.scrolls})"
