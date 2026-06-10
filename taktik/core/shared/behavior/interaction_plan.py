"""Per-target interaction plan — the resolved INTENT for one profile/account.

The seed of the platform-agnostic `InteractionPlan` model (see
`taktik-docs/technical/interaction-model-redesign.md`): the engine turns a config + the
rolled interactions into a concrete, per-profile plan, separating the WHAT (how many likes,
which story slide to like) from the HOW (gestures/timing, handled by the humanization engine).

Three facts this fixes, all caught on real runs via the step telemetry:
- likes were never sampled in [min, max] — the loop always targeted max (≈ always 3);
- the like target ignored profile SIZE — 3 likes on a 10-post account (30% of the feed!)
  reads the same as 3 likes on a 500-post account; the count is now proportional to how
  many posts the profile has (a small account gets few likes, a large one can take more);
- story-like liked EVERY watched slide — a human leaves at most one like on a story.

Pure + dependency-free (only stdlib `random`/`math`) so it's unit-testable and reusable by
every workflow (Instagram now, TikTok later) and, in time, by the Taktik-Agent orchestrator.
"""

from dataclasses import dataclass
import math
import random


@dataclass
class InteractionPlan:
    """The resolved plan for ONE target. Built from config + rolled interactions."""

    like_target: int          # number of posts/videos to like this profile (0 = none)
    do_follow: bool
    do_comment: bool
    max_comments: int
    do_watch_story: bool
    story_like_slot: int      # 0-based index of the ONE watched slide to like (-1 = none)
    max_story_slides: int


def proportional_like_cap(posts_count: int, min_likes: int, max_likes: int) -> int:
    """Scale the per-profile like ceiling to how many posts the profile has.

    A 10-post account caps low (~2), a 500-post account can take the full max (~8) — so we
    never like a third of someone's tiny feed nor leave only 3 likes on a 500-post account.
    Log curve fit to the operator intuition (10 posts -> 2 likes, 500 posts -> 8 likes),
    clamped to [min_likes, max_likes] (max_likes is the hard absolute ceiling)."""
    hi = max(0, int(max_likes))
    lo = min(max(0, int(min_likes)), hi)
    if hi == 0:
        return 0
    if not posts_count or posts_count <= 0:
        return lo  # unknown post count -> stay conservative at the floor
    scaled = round(3.5 * math.log10(posts_count) - 1.5)
    return max(lo, min(hi, scaled))


def sample_like_target(min_likes: int, max_likes: int, *, posts_count=None, rng=None) -> int:
    """Sample how many posts to like this profile.

    When `posts_count` is known the target is PROPORTIONAL to the profile size
    (`proportional_like_cap`) with a -1 jitter for variety; when it's unknown we fall back
    to the legacy uniform [min, max] draw (back-compat). `max_likes` is always the hard
    ceiling (an explicit max=0 means "no likes"); `min_likes` is the floor."""
    r = rng or random
    # max is the hard ceiling: an explicit max=0 means "no likes" (must not be
    # overridden by a default min=1); min is clamped DOWN to it if misconfigured.
    hi = max(0, int(max_likes))
    lo = min(max(0, int(min_likes)), hi)
    if hi == 0:
        return 0
    if not posts_count or posts_count <= 0:
        return r.randint(lo, hi)
    cap = proportional_like_cap(posts_count, lo, hi)
    # Keep a little variety around the proportional target without drifting below the floor.
    low = max(lo, cap - 1)
    return r.randint(low, cap)


def sample_story_like_slot(max_slides: int, *, rng=None) -> int:
    """Pick the single story slide (0-based) to like, when a story-like is planned.

    A human who likes a story likes ONE slide that resonates — never all of them. Returns a
    varied index in [0, max_slides-1]; the caller likes at most that one slide (with a
    last-slide fallback if the real story is shorter than the sampled index)."""
    r = rng or random
    n = max(1, int(max_slides))
    return r.randint(0, n - 1)


def build_interaction_plan(config: dict, interactions_to_do, *, posts_count=None, rng=None) -> InteractionPlan:
    """Resolve a per-profile `InteractionPlan` from the action config + the rolled
    `interactions_to_do` list (['like','follow','comment','story','story_like']).

    `interactions_to_do` carries the probability rolls (which intents fire for this profile);
    this function turns the "yes" intents into concrete quantities (a like target sampled
    PROPORTIONALLY to `posts_count` when known, the single story-like slot). Quantities come
    from `min/max_likes_per_profile` and `max_stories_per_profile`; the gesture execution
    stays in the engine."""
    intents = set(interactions_to_do or [])
    do_like = 'like' in intents
    do_watch = ('story' in intents) or ('story_like' in intents)
    do_story_like = 'story_like' in intents

    min_likes = config.get('min_likes_per_profile', 1)
    max_likes = config.get('max_likes_per_profile', 3)
    max_slides = config.get('max_stories_per_profile', 3)

    like_target = sample_like_target(min_likes, max_likes, posts_count=posts_count, rng=rng) if do_like else 0
    story_slot = sample_story_like_slot(max_slides, rng=rng) if (do_watch and do_story_like) else -1

    return InteractionPlan(
        like_target=like_target,
        do_follow='follow' in intents,
        do_comment='comment' in intents,
        max_comments=int(config.get('max_comments_per_profile', 1)),
        do_watch_story=do_watch,
        story_like_slot=story_slot,
        max_story_slides=int(max_slides),
    )


__all__ = [
    "InteractionPlan",
    "proportional_like_cap",
    "sample_like_target",
    "sample_story_like_slot",
    "build_interaction_plan",
]
