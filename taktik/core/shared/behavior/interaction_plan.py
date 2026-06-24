"""Per-target interaction plan — the resolved INTENT for one profile/account.

The seed of the platform-agnostic `InteractionPlan` model (see
`internal docs`): the engine turns a config + the
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
    do_story_like: bool       # whether to like story slides at all (count resolved at open)
    max_story_likes: int      # hard ceiling for the proportional story-like count


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


def sample_story_like_count(slides_available: int, max_likes: int = 3, *, rng=None) -> int:
    """How many story slides to like, PROPORTIONAL to how many slides the story has.

    A human leaves a couple of likes on a long story and none/one on a short one — not a
    flat "exactly one" regardless of length, nor "all of them". ~1 like per 5 slides with a
    fractional jitter (so it varies), clamped to [0, min(max_likes, slides)]. Returns 0 when
    the slide count is unknown/zero. Anchors: 2 slides -> 0-1, 6 -> 1-2, 12 -> 2-3."""
    r = rng or random
    n = int(slides_available or 0)
    if n <= 0:
        return 0
    cap = max(0, int(max_likes))
    if cap == 0:
        return 0
    expected = n / 5.0
    base = int(expected)
    count = base + (1 if r.random() < (expected - base) else 0)
    return max(0, min(count, cap, n))


def sample_story_like_slots(slides_available: int, count: int, *, rng=None) -> list:
    """Pick `count` DISTINCT story slide indices (0-based, sorted) to like, varied across
    the story. Returns [] when count<=0 or no slides. Caps count at the slide total."""
    r = rng or random
    n = max(0, int(slides_available or 0))
    k = max(0, min(int(count or 0), n))
    if k == 0:
        return []
    return sorted(r.sample(range(n), k))


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
    max_story_likes = int(config.get('max_story_likes_per_profile', 3))

    like_target = sample_like_target(min_likes, max_likes, posts_count=posts_count, rng=rng) if do_like else 0
    # Kept for back-compat (single-slot fallback when the slide count can't be read at open).
    story_slot = sample_story_like_slot(max_slides, rng=rng) if (do_watch and do_story_like) else -1

    return InteractionPlan(
        like_target=like_target,
        do_follow='follow' in intents,
        do_comment='comment' in intents,
        max_comments=int(config.get('max_comments_per_profile', 1)),
        do_watch_story=do_watch,
        story_like_slot=story_slot,
        max_story_slides=int(max_slides),
        do_story_like=(do_watch and do_story_like),
        max_story_likes=max_story_likes,
    )


__all__ = [
    "InteractionPlan",
    "proportional_like_cap",
    "sample_like_target",
    "sample_story_like_slot",
    "sample_story_like_count",
    "sample_story_like_slots",
    "build_interaction_plan",
]
