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


__all__ = ["DOUBLE_TAP_LIKE_PROB", "should_double_tap_like"]
