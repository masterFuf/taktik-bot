"""How a human likes a post — not always the same gesture.

Some likes are a tap on the like button, others a double-tap on the image. We
alternate between the two by chance so the touch pattern isn't a fingerprint.
Shared by the feed and the profile-posts (like workflow) paths so both behave
identically. Tunable; will move to the behaviour profile.
"""

import random

# Share of likes done via the image double-tap (vs the like button).
DOUBLE_TAP_LIKE_PROB = 0.45


def should_double_tap_like(rng=None) -> bool:
    """Pick the like method at random — True = image double-tap, False = like button."""
    return (rng or random).random() < DOUBLE_TAP_LIKE_PROB


#: Chance that a walk through a profile's posts likes the post on screen, before the position factor.
POST_LIKE_BASE_PROB = 0.70


def post_like_probability(position: int) -> float:
    """How likely the post at `position` (1 for the first new post seen) is liked: a human likes the
    first posts of a profile a little less often than the ones they scroll to."""
    position_factor = 0.8 if position <= 2 else (1.0 if position <= 5 else 1.2)
    return POST_LIKE_BASE_PROB * position_factor


def should_like_this_post(*, likes_owed: int, posts_left: int, position: int, rng=None) -> bool:
    """Does the walk through a profile's posts like the post on screen?

    The plan of the profile has already decided HOW MANY likes it gets (`likes_owed` still to give);
    this only chooses WHICH posts. The draw (`post_like_probability`) keeps the choice natural, but
    once the likes owed reach the posts left to see (this one included), each of them is liked:
    otherwise a draw could undo the plan, as it did on a one-post profile 44 % of the time.
    """
    if likes_owed <= 0:
        return False
    if likes_owed >= posts_left:
        return True
    return (rng or random).random() < post_like_probability(position)


__all__ = [
    "DOUBLE_TAP_LIKE_PROB",
    "POST_LIKE_BASE_PROB",
    "post_like_probability",
    "should_double_tap_like",
    "should_like_this_post",
]
