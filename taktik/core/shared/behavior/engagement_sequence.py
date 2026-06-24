"""Per-post engagement choreography — not always the same order.

A human doesn't engage with a post the same way every time: sometimes they like it
straight away (double-tap), then open the caption to read it, then comment; other times
they read the description first, then like, then comment; sometimes they just like + comment
without reading; sometimes they read and like but don't comment.

`plan_engagement_sequence` returns an ORDERED list of sub-actions from {'read', 'like',
'comment'} for one post, picked from weighted patterns. The caller executes the steps in
that order (read = open+read the description then reframe; like = like the post; comment =
post a comment). Pure + dependency-free (stdlib `random`) so it's unit-testable and reusable
(Instagram now; the Taktik-Agent could later impose a pattern per target).

See `internal docs` §4.
"""

import random


# Weighted patterns. Each entry: (ordered steps, weight). Only steps relevant to the
# decided intents are used (a pattern set is chosen by which intents fire).
_LIKE_AND_COMMENT = [
    (('like', 'read', 'comment'), 0.30),   # A — like straight away, read, then comment
    (('read', 'like', 'comment'), 0.30),   # B — read the description, like, then comment
    (('like', 'comment'), 0.25),           # C — like + comment, no deliberate read
    (('read', 'comment', 'like'), 0.15),   # E — read, comment on it, then a like
]
_LIKE_ONLY = [
    (('like',), 0.45),                     # just a like
    (('read', 'like'), 0.30),              # D — read the description, then like
    (('like', 'read'), 0.25),              # like, then linger on the caption
]
_COMMENT_ONLY = [
    (('read', 'comment'), 0.60),           # read then comment (grounded)
    (('comment',), 0.40),
]


def _weighted_choice(patterns, rng):
    steps, weights = zip(*patterns)
    return list(rng.choices(steps, weights=weights, k=1)[0])


def plan_engagement_sequence(do_like: bool, do_comment: bool, *, rng=None) -> list:
    """Return the ordered engagement steps for one post (a varied choreography).

    Steps are a subset/order of ['read', 'like', 'comment']. Empty when nothing to do."""
    r = rng or random
    if do_like and do_comment:
        return _weighted_choice(_LIKE_AND_COMMENT, r)
    if do_like:
        return _weighted_choice(_LIKE_ONLY, r)
    if do_comment:
        return _weighted_choice(_COMMENT_ONLY, r)
    return []


__all__ = ["plan_engagement_sequence"]
