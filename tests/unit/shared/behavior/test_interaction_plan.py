"""Per-target interaction plan — sampled like target + single story-like slot."""

import random

from taktik.core.shared.behavior.interaction_plan import (
    InteractionPlan,
    RelevanceGating,
    apply_relevance_gating,
    proportional_like_cap,
    sample_like_target,
    sample_story_like_slot,
    sample_story_like_count,
    sample_story_like_slots,
    build_interaction_plan,
    interaction_plan_from_payload,
)


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
