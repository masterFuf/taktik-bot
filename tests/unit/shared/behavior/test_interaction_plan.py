"""Per-target interaction plan — sampled like target + single story-like slot."""

import random

from taktik.core.shared.behavior.interaction_plan import (
    InteractionPlan,
    sample_like_target,
    sample_story_like_slot,
    build_interaction_plan,
)


# ─── sample_like_target ──────────────────────────────────────────────────────

def test_like_target_within_range_and_varies():
    rng = random.Random(1)
    vals = {sample_like_target(1, 3, rng=rng) for _ in range(200)}
    assert vals == {1, 2, 3}                       # not always the max — full spread
    assert all(1 <= v <= 3 for v in vals)


def test_like_target_distribution_not_always_max():
    rng = random.Random(7)
    n = 3000
    threes = sum(sample_like_target(1, 3, rng=rng) == 3 for _ in range(n))
    assert 0.25 < threes / n < 0.40                # ≈ 1/3, the OLD bug was ~100%


def test_like_target_clamps_inverted_and_negative():
    assert sample_like_target(5, 2) == 2              # min clamped DOWN to the max ceiling
    assert sample_like_target(-4, 0) == 0             # negatives clamped to >=0


def test_like_target_explicit_max_zero_disables():
    # An explicit max=0 means "no likes" — a default min=1 must not override it.
    assert sample_like_target(1, 0) == 0
    assert all(sample_like_target(1, 0) == 0 for _ in range(50))


# ─── sample_story_like_slot ──────────────────────────────────────────────────

def test_story_slot_in_range():
    rng = random.Random(3)
    slots = {sample_story_like_slot(4, rng=rng) for _ in range(100)}
    assert slots <= {0, 1, 2, 3} and len(slots) > 1   # varied, never out of range


def test_story_slot_handles_min_one():
    assert sample_story_like_slot(0) == 0             # at least one slot


# ─── build_interaction_plan ──────────────────────────────────────────────────

def _cfg():
    return {'min_likes_per_profile': 1, 'max_likes_per_profile': 3,
            'max_stories_per_profile': 3, 'max_comments_per_profile': 2}


def test_plan_likes_only_when_like_intent():
    p = build_interaction_plan(_cfg(), ['follow'], rng=random.Random(1))
    assert p.like_target == 0 and p.do_follow is True and p.do_comment is False

    p2 = build_interaction_plan(_cfg(), ['like'], rng=random.Random(1))
    assert 1 <= p2.like_target <= 3


def test_plan_story_like_slot_only_when_story_like_intent():
    # story watched but NOT liked → no slot
    p = build_interaction_plan(_cfg(), ['story'], rng=random.Random(2))
    assert p.do_watch_story is True and p.story_like_slot == -1
    # story_like rolled → a single slot in range
    p2 = build_interaction_plan(_cfg(), ['story', 'story_like'], rng=random.Random(2))
    assert p2.do_watch_story is True and 0 <= p2.story_like_slot <= 2


def test_plan_comment_carries_max():
    p = build_interaction_plan(_cfg(), ['comment'], rng=random.Random(1))
    assert p.do_comment is True and p.max_comments == 2


def test_plan_is_dataclass():
    p = build_interaction_plan(_cfg(), [], rng=random.Random(1))
    assert isinstance(p, InteractionPlan)
    assert p.like_target == 0 and p.story_like_slot == -1 and p.do_watch_story is False
