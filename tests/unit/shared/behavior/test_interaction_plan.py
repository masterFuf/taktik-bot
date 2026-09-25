"""Per-target interaction plan — sampled like target + single story-like slot."""

import random

import pytest

from taktik.core.shared.behavior.interaction_plan import (
    InteractionPlan,
    RelevanceGating,
    apply_relevance_gating,
    like_target_law,
    proportional_like_cap,
    sample_like_target,
    tilt_like_law,
    sample_story_like_slot,
    sample_story_like_count,
    sample_story_like_slots,
    build_interaction_plan,
    interaction_plan_from_payload,
)
from taktik.core.shared.behavior.session_state import BehaviorSessionState


def _plan(**over):
    base = dict(
        like_target=3, do_follow=True, do_comment=True, max_comments=1,
        do_watch_story=True, story_like_slot=-1, max_story_slides=3,
        do_story_like=False, max_story_likes=3,
    )
    base.update(over)
    return InteractionPlan(**base)


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
    # The two reference points: a small account likes few, a big one more.
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
    # 500 posts -> ~8: up to two under the cap (the old cap-1/cap coin put every profile of a
    # run on the same two counts), never above it.
    assert big <= {6, 7, 8}
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


# ─── sample_story_like_count / slots (proportional to slide count) ────────────

def test_story_like_count_proportional_and_bounded():
    rng = random.Random(4)
    # Many samples per slide-count: the count must stay within [0, min(max, slides)].
    for slides, expect_max in [(2, 1), (6, 2), (12, 3)]:
        vals = {sample_story_like_count(slides, 3, rng=rng) for _ in range(300)}
        assert min(vals) >= 0
        assert max(vals) <= expect_max
    # Longer stories yield more likes on average than short ones.
    rng2 = random.Random(9)
    avg = lambda n, mx: sum(sample_story_like_count(n, mx, rng=rng2) for _ in range(500)) / 500
    assert avg(12, 5) > avg(2, 5)


def test_story_like_count_zero_when_unknown_or_capped():
    assert sample_story_like_count(0, 3) == 0          # unknown slide count
    assert sample_story_like_count(10, 0) == 0         # max 0 disables
    assert sample_story_like_count(8, 3) <= 3          # never exceeds the cap


def test_story_like_slots_distinct_sorted_in_range():
    rng = random.Random(2)
    slots = sample_story_like_slots(10, 3, rng=rng)
    assert len(slots) == 3 and len(set(slots)) == 3    # distinct
    assert slots == sorted(slots)                      # sorted
    assert all(0 <= s < 10 for s in slots)             # in range


def test_story_like_slots_clamped_and_empty():
    assert sample_story_like_slots(2, 5) and len(sample_story_like_slots(2, 5)) == 2  # capped at slides
    assert sample_story_like_slots(5, 0) == []
    assert sample_story_like_slots(0, 3) == []


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


# ─── apply_relevance_gating ──────────────────────────────────────────────────

def test_gating_disabled_is_passthrough():
    plan = _plan()
    g = apply_relevance_gating(plan, {"relevant": False, "score": 0.1}, {"enabled": False})
    assert g.active is False and g.skip is False and g.plan is plan


def test_gating_no_verdict_fails_open():
    plan = _plan()
    g = apply_relevance_gating(plan, None, {"enabled": True})
    assert g.active is False and g.skip is False and g.plan is plan


def test_gating_skips_irrelevant_profile():
    plan = _plan()
    g = apply_relevance_gating(plan, {"relevant": False, "score": 0.2}, {"enabled": True})
    assert g.active and g.would_skip and g.skip and g.plan is plan  # plan untouched, caller skips


def test_gating_skips_below_min_score():
    plan = _plan()
    g = apply_relevance_gating(
        plan, {"relevant": True, "score": 0.3, "follow": True, "like": True},
        {"enabled": True, "minScore": 0.5},
    )
    assert g.skip is True


def test_gating_keeps_relevant_above_threshold():
    plan = _plan()
    g = apply_relevance_gating(
        plan, {"relevant": True, "score": 0.8, "follow": True, "comment": True, "like": True},
        {"enabled": True, "minScore": 0.5},
    )
    assert g.would_skip is False and g.skip is False and not g.masked


def test_gating_masks_intents_the_verdict_advises_against():
    plan = _plan(like_target=3, do_follow=True, do_comment=True)
    g = apply_relevance_gating(
        plan,
        {"relevant": True, "score": 0.9, "follow": False, "comment": True, "like": False},
        {"enabled": True, "minScore": 0.4},
    )
    assert set(g.masked) == {"follow", "like"}
    assert g.plan.do_follow is False and g.plan.like_target == 0
    assert g.plan.do_comment is True  # the one the verdict endorsed survives


def test_gating_never_adds_intents():
    # Verdict says follow, but the plan never planned to follow → stays False (upper bound owned
    # by probabilities/quotas, the gate only ever REMOVES).
    plan = _plan(do_follow=False, do_comment=False, like_target=0)
    g = apply_relevance_gating(
        plan, {"relevant": True, "score": 0.9, "follow": True, "comment": True, "like": True},
        {"enabled": True},
    )
    assert g.plan.do_follow is False and g.plan.do_comment is False and g.plan.like_target == 0


def test_gating_dry_run_reports_but_changes_nothing():
    plan = _plan()
    g = apply_relevance_gating(
        plan, {"relevant": False, "score": 0.1},
        {"enabled": True, "dryRun": True},
    )
    assert g.would_skip is True   # would have skipped
    assert g.skip is False        # but doesn't
    assert g.plan is plan         # and leaves the plan intact


def test_gating_dry_run_reports_masking_without_applying():
    plan = _plan(do_follow=True, like_target=2)
    g = apply_relevance_gating(
        plan, {"relevant": True, "score": 0.9, "follow": False, "like": False, "comment": True},
        {"enabled": True, "dryRun": True},
    )
    assert set(g.masked) == {"follow", "like"}
    assert g.plan is plan and g.plan.do_follow is True and g.plan.like_target == 2


def test_injected_plan_is_clamped_to_local_execution_bounds():
    plan = interaction_plan_from_payload(
        {
            "likes": 99,
            "follow": True,
            "comment": True,
            "maxComments": 8,
            "watchStory": True,
            "likeStory": True,
            "maxStorySlides": 12,
            "maxStoryLikes": 7,
        },
        {
            "max_likes_per_profile": 3,
            "max_comments_per_profile": 1,
            "max_stories_per_profile": 4,
            "max_story_likes_per_profile": 2,
        },
        rng=random.Random(7),
    )

    assert plan.like_target == 3
    assert plan.do_follow is True
    assert plan.max_comments == 1
    assert plan.max_story_slides == 4
    assert plan.max_story_likes == 2
    assert 0 <= plan.story_like_slot < 4


def test_injected_plan_cannot_bypass_operator_capability_mask():
    plan = interaction_plan_from_payload(
        {
            "likes": 3,
            "follow": True,
            "comment": True,
            "maxComments": 1,
            "watchStory": True,
            "likeStory": True,
            "maxStorySlides": 3,
            "maxStoryLikes": 1,
        },
        {
            "max_likes_per_profile": 3,
            "max_comments_per_profile": 1,
            "max_stories_per_profile": 3,
            "max_story_likes_per_profile": 1,
            "ai_decision_capabilities": {
                "like": False,
                "follow": False,
                "comment": False,
                "watchStories": True,
                "likeStories": False,
            },
        },
    )

    assert plan.like_target == 0
    assert plan.do_follow is False
    assert plan.do_comment is False
    assert plan.do_watch_story is True
    assert plan.do_story_like is False


# ─── like count: spread and session lean, same means (H4) ─────────────────────


def _law_mean(law):
    return sum(count * p for count, p in law)


def _law_sd(law):
    mean = _law_mean(law)
    return sum(p * (count - mean) ** 2 for count, p in law) ** 0.5


def _old_mean_and_sd(lo, hi, posts_count):
    """The historical draw: uniform [lo, hi], or uniform [max(lo, cap - 1), cap]."""
    hi = max(0, hi)
    lo = min(max(0, lo), hi)
    if not posts_count:
        low, high = lo, hi
    else:
        cap = proportional_like_cap(posts_count, lo, hi)
        low, high = max(lo, cap - 1), cap
    n = high - low + 1
    return (low + high) / 2, ((n * n - 1) / 12) ** 0.5


@pytest.mark.parametrize("lo, hi", [(1, 3), (1, 8), (2, 6), (0, 2), (3, 3), (1, 1)])
@pytest.mark.parametrize("posts_count", [None, 5, 10, 14, 60, 200, 500, 5000])
def test_like_law_keeps_the_historical_mean_and_never_narrows(lo, hi, posts_count):
    law = like_target_law(lo, hi, posts_count=posts_count)
    old_mean, old_sd = _old_mean_and_sd(lo, hi, posts_count)
    assert abs(sum(p for _, p in law) - 1.0) < 1e-12
    assert abs(_law_mean(law) - old_mean) < 1e-9
    assert _law_sd(law) >= old_sd - 1e-9
    assert all(lo <= count <= hi for count, _ in law)
    if posts_count:
        assert max(count for count, _ in law) <= proportional_like_cap(posts_count, lo, hi)


def test_like_law_spreads_when_the_floor_leaves_room():
    law = like_target_law(1, 3, posts_count=200)       # cap 3: counts 1, 2, 3
    assert [count for count, _ in law] == [1, 2, 3]
    assert _law_sd(law) > 1.25 * 0.5                    # the old coin between 2 and 3


@pytest.mark.parametrize("appetite", [0.2, 0.5, 0.85])
def test_opposite_leans_average_back_to_the_law(appetite):
    for posts_count in (None, 200, 500):
        law = like_target_law(1, 8, posts_count=posts_count)
        up, down = tilt_like_law(law, appetite), tilt_like_law(law, -appetite)
        assert [c for c, _ in up] == [c for c, _ in law]            # same support: caps hold
        assert all(p > 0 for _, p in up + down)
        assert abs(sum(p for _, p in up) - 1.0) < 1e-12
        for (count, p), (_, pu), (_, pd) in zip(law, up, down):
            assert abs((pu + pd) / 2 - p) < 1e-12
        assert _law_mean(up) > _law_mean(law) > _law_mean(down)


def test_a_non_number_appetite_is_ignored():
    from unittest.mock import MagicMock

    law = like_target_law(1, 3)
    assert tilt_like_law(law, MagicMock()) == law
    assert tilt_like_law(law, True) == law
    assert tilt_like_law(law, float("nan")) == law


@pytest.mark.parametrize("posts_count", [None, 200, 500])
def test_sessions_differ_but_the_long_run_mean_and_the_caps_hold(posts_count):
    lo, hi, per_session, sessions = 1, 8, 30, 3000
    old_mean, old_sd = _old_mean_and_sd(lo, hi, posts_count)
    all_values, session_means = [], []
    for s in range(sessions):
        appetite = BehaviorSessionState(seed=90_000 + s).like_appetite
        rng = random.Random(s)
        values = [sample_like_target(lo, hi, posts_count=posts_count, rng=rng, appetite=appetite)
                  for _ in range(per_session)]
        all_values.extend(values)
        session_means.append(sum(values) / per_session)
    mean = sum(all_values) / len(all_values)
    assert abs(mean - old_mean) < 0.03 * old_mean
    assert max(all_values) <= (proportional_like_cap(posts_count, lo, hi) if posts_count else hi)
    assert min(all_values) >= lo
    spread = (sum((m - mean) ** 2 for m in session_means) / sessions) ** 0.5
    assert spread > 1.5 * old_sd / per_session ** 0.5       # the old draw: sampling noise only


def test_session_like_appetite_is_seeded_bounded_and_neutral_in_strict_mode():
    first, again = BehaviorSessionState(seed=7), BehaviorSessionState(seed=7)
    assert first.like_appetite == again.like_appetite
    values = [BehaviorSessionState(seed=s).like_appetite for s in range(2000)]
    assert all(-0.85 < v < 0.85 for v in values)
    assert abs(sum(values) / len(values)) < 0.03
    assert len(set(values)) > 500
    assert BehaviorSessionState(seed=7, strict_regression=True).like_appetite == 0.0


def test_reading_the_appetite_does_not_shift_the_seeded_gestures():
    plain, read = BehaviorSessionState(seed=31), BehaviorSessionState(seed=31)
    _ = read.like_appetite
    for _ in range(20):
        a = plain.choose_scroll_mode(context="feed")
        b = read.choose_scroll_mode(context="feed")
        assert a == b


def test_plan_passes_the_session_appetite_to_the_like_target():
    cfg = {'min_likes_per_profile': 1, 'max_likes_per_profile': 8, 'max_stories_per_profile': 3}
    eager = [build_interaction_plan(cfg, ['like'], posts_count=500, rng=random.Random(i),
                                    appetite=0.85).like_target for i in range(400)]
    shy = [build_interaction_plan(cfg, ['like'], posts_count=500, rng=random.Random(i),
                                  appetite=-0.85).like_target for i in range(400)]
    assert sum(eager) > sum(shy)
    assert max(eager) <= 8 and min(shy) >= 6
