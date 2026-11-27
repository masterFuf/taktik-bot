"""Likes whose effect the screen did not show: a few in a row leave the posts, more stop the run.

A like is a gesture, then a reading of its heart. When Instagram changed how a heart says it is liked
(« J’aime déjà », `selected` false, decided on its servers), no like was seen any more: a run tapped
its heart after each double tap and took the like back, and counted nothing after each tap, so its
caps no longer held. 168 likes went that way in one evening, with nothing to say so. One like not
seen means little (a slow screen, a post that moved); several in a row mean this run no longer knows
what it does.

Two thresholds, because two things can be wrong. Some posts do not show their like: on a Pixel 3a,
half the double taps on a video were read as not given, on 58 of them, while photos showed every one.
Stopping the run on three of those ended runs that liked well everywhere else. So three in a row ask
to leave the posts being liked (`leave_posts_asked`: the walk of a profile's posts goes to the next
profile), and the run stops only when the next profiles show none either: nine in a row, no like seen
in between. That is when the reading itself no longer works, which is what cost the 168 likes.

The first likes not seen of a run keep their screen (`screen_to_keep`): the dump and the picture at
that moment are the only way to tell a like not given from a like the heart does not say.

The count lives here, at module level, and not in a workflow or in `LikeOrchestration`: the Feed, a
profile's posts and the hashtag pass all like through that class, each with its own instance, and a
run can chain them. Like the other counters of a run (`miss_capture`, `screen_ring`),
`run_start.begin_run` clears it. It only counts: the like calls `like_seen` or `like_not_seen` once
per gesture played. No gesture (a heart that could not be shown) and a post liked already say nothing
either way. In Symfony terms: a small stateful service, reset between two messages.
"""

from __future__ import annotations

from taktik.core.shared.diagnostics import run_halt

#: Likes not seen in a row before the posts being liked are left. Same reasoning as the three
#: unfollows of `workflows/automation/unfollow/workflow.py`: two can be chance, three are not.
UNCONFIRMED_LIKES_BEFORE_LEAVING = 3

#: Likes not seen in a row before the run stops: three lists of posts left one after the other,
#: without one like seen. The most a run can give without counting them.
UNCONFIRMED_LIKES_BEFORE_HALT = 9

#: Screens kept per run. Each costs a dump and a picture (about a second on a slow phone).
SCREENS_KEPT_PER_RUN = 3

_not_seen_in_a_row = 0
_leave_posts = False
_screens_kept = 0


def reinitialiser() -> None:
    """A new run starts with nothing to hold against it. Called by `run_start.begin_run`."""
    global _not_seen_in_a_row, _leave_posts, _screens_kept
    _not_seen_in_a_row = 0
    _leave_posts = False
    _screens_kept = 0


def like_seen() -> None:
    """A like's heart said liked: likes do show on this screen."""
    global _not_seen_in_a_row, _leave_posts
    _not_seen_in_a_row = 0
    _leave_posts = False


def like_not_seen() -> None:
    """A like gesture was played and its heart did not say liked. Every third in a row asks to leave
    the posts; the ninth sets the latch of the run."""
    global _not_seen_in_a_row, _leave_posts
    _not_seen_in_a_row += 1
    if _not_seen_in_a_row >= UNCONFIRMED_LIKES_BEFORE_HALT:
        run_halt.demander_arret(
            run_halt.LIKE_UNCONFIRMED,
            f"{_not_seen_in_a_row} likes in a row not confirmed by the screen",
        )
    elif _not_seen_in_a_row % UNCONFIRMED_LIKES_BEFORE_LEAVING == 0:
        _leave_posts = True


def posts_entered() -> None:
    """A list of posts is entered: what was asked of the one before no longer holds. The count in a
    row goes on: it is the run's."""
    global _leave_posts
    _leave_posts = False


def leave_posts_asked() -> bool:
    """The likes of the posts being walked no longer show: no next post there."""
    return _leave_posts


def screen_to_keep() -> bool:
    """Whether this like not seen keeps its screen: the first `SCREENS_KEPT_PER_RUN` of a run do.
    Asking counts: call it once per like not seen."""
    global _screens_kept
    if _screens_kept >= SCREENS_KEPT_PER_RUN:
        return False
    _screens_kept += 1
    return True


__all__ = [
    "UNCONFIRMED_LIKES_BEFORE_LEAVING", "UNCONFIRMED_LIKES_BEFORE_HALT", "SCREENS_KEPT_PER_RUN",
    "like_seen", "like_not_seen", "posts_entered", "leave_posts_asked", "screen_to_keep", "reinitialiser",
]
