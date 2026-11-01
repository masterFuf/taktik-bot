"""Several likes in a row whose effect the screen did not show stop the run.

A like is a gesture, then a reading of its heart. When Instagram changed how a heart says it is liked
(« J’aime déjà », `selected` false, decided on its servers), no like was seen any more: a run tapped
its heart after each double tap and took the like back, and counted nothing after each tap, so its
caps no longer held. 168 likes went that way in one evening, with nothing to say so. One like not
seen means little (a slow screen, a post that moved); several in a row mean this run no longer knows
what it does.

The count lives here, at module level, and not in a workflow or in `LikeOrchestration`: the Feed, a
profile's posts and the hashtag pass all like through that class, each with its own instance, and a
run can chain them. Like the other counters of a run (`miss_capture`, `screen_ring`),
`run_start.begin_run` clears it. It only counts: the like calls `like_seen` or `like_not_seen` once
per gesture played. No gesture (a heart that could not be shown) and a post liked already say nothing
either way. In Symfony terms: a small stateful service, reset between two messages.
"""

from __future__ import annotations

from taktik.core.shared.diagnostics import run_halt

#: Likes not seen in a row before the run stops. Same reasoning as the three unfollows of
#: `workflows/automation/unfollow/workflow.py`: two can be chance, three are not.
UNCONFIRMED_LIKES_BEFORE_HALT = 3

_not_seen_in_a_row = 0


def reinitialiser() -> None:
    """A new run starts with nothing to hold against it. Called by `run_start.begin_run`."""
    global _not_seen_in_a_row
    _not_seen_in_a_row = 0


def like_seen() -> None:
    """A like's heart said liked: likes do show on this screen."""
    global _not_seen_in_a_row
    _not_seen_in_a_row = 0


def like_not_seen() -> None:
    """A like gesture was played and its heart did not say liked. The third in a row sets the latch."""
    global _not_seen_in_a_row
    _not_seen_in_a_row += 1
    if _not_seen_in_a_row >= UNCONFIRMED_LIKES_BEFORE_HALT:
        run_halt.demander_arret(
            run_halt.LIKE_UNCONFIRMED,
            f"{_not_seen_in_a_row} likes in a row not confirmed by the screen",
        )


__all__ = ["UNCONFIRMED_LIKES_BEFORE_HALT", "like_seen", "like_not_seen", "reinitialiser"]
