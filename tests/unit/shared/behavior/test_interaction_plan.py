"""Per-target interaction plan — sampled like target + single story-like slot."""

import random

from taktik.core.shared.behavior.interaction_plan import (
    InteractionPlan,
    proportional_like_cap,
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


# ─── proportional_like_cap (likes scale with profile size) ───────────────────

def test_proportional_cap_matches_operator_anchors():
    # The two reference points Kevin gave: a small account likes few, a big one more.
    assert proportional_like_cap(10, 1, 8) == 2
    assert proportional_like_cap(500, 1, 8) == 8


def test_proportional_cap_floor_and_ceiling():
    assert proportional_like_cap(3, 1, 8) == 1          # tiny account -> floor
    assert proportional_like_cap(100000, 1, 8) == 8     # huge account -> hard ceiling
    assert proportional_like_cap(500, 2, 6) == 6        # never exceeds max
    assert proportional_like_cap(10, 4, 8) == 4         # never below the explicit floor


def test_proportional_cap_is_monotonic_non_decreasing():
    caps = [proportional_like_cap(n, 1, 8) for n in (5, 10, 50, 100, 300, 500, 1000)]
    assert caps == sorted(caps)                          # more posts never means fewer likes


def test_proportional_cap_unknown_or_zero_posts_is_floor():
    assert proportional_like_cap(0, 1, 8) == 1
    assert proportional_like_cap(None, 2, 8) == 2


def test_proportional_cap_max_zero_disables():
    assert proportional_like_cap(500, 1, 0) == 0


def test_sample_like_target_proportional_stays_near_cap():
    rng = random.Random(11)
    small = {sample_like_target(1, 8, posts_count=10, rng=rng) for _ in range(200)}
    big = {sample_like_target(1, 8, posts_count=500, rng=rng) for _ in range(200)}
    assert small <= {1, 2}                               # 10 posts -> ~2, never the full max
    assert big <= {7, 8}                                 # 500 posts -> ~8
    assert max(big) > max(small)                         # bigger profile gets more likes


def test_sample_like_target_without_posts_is_legacy_uniform():
    # Back-compat: no post-count info -> the old uniform [min,max] spread.
    rng = random.Random(5)
    vals = {sample_like_target(1, 3, rng=rng) for _ in range(200)}
    assert vals == {1, 2, 3}


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


def test_plan_like_target_proportional_to_posts_count():
    cfg = {'min_likes_per_profile': 1, 'max_likes_per_profile': 8, 'max_stories_per_profile': 3}
    small = build_interaction_plan(cfg, ['like'], posts_count=10, rng=random.Random(1))
    big = build_interaction_plan(cfg, ['like'], posts_count=500, rng=random.Random(1))
    assert small.like_target <= 2
    assert big.like_target >= 7
    # Without posts_count the legacy uniform draw still applies (back-compat).
    legacy = build_interaction_plan(cfg, ['like'], rng=random.Random(1))
    assert 1 <= legacy.like_target <= 8


def test_plan_comment_carries_max():
    p = build_interaction_plan(_cfg(), ['comment'], rng=random.Random(1))
    assert p.do_comment is True and p.max_comments == 2


def test_plan_is_dataclass():
    p = build_interaction_plan(_cfg(), [], rng=random.Random(1))
    assert isinstance(p, InteractionPlan)
    assert p.like_target == 0 and p.story_like_slot == -1 and p.do_watch_story is False
