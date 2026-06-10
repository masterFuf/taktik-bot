"""Per-target interaction plan — the resolved INTENT for one profile/account.

The seed of the platform-agnostic `InteractionPlan` model (see
`taktik-docs/technical/interaction-model-redesign.md`): the engine turns a config + the
rolled interactions into a concrete, per-profile plan, separating the WHAT (how many likes,
which story slide to like) from the HOW (gestures/timing, handled by the humanization engine).

Two facts this fixes, both caught on real runs via the step telemetry:
- likes were never sampled in [min, max] — the loop always targeted max (≈ always 3);
- story-like liked EVERY watched slide — a human leaves at most one like on a story.

Pure + dependency-free (only stdlib `random`) so it's unit-testable and reusable by every
workflow (Instagram now, TikTok later) and, in time, by the Taktik-Agent orchestrator.
"""

from dataclasses import dataclass
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


def sample_like_target(min_likes: int, max_likes: int, *, rng=None) -> int:
    """Sample how many posts to like this profile, uniformly in [min, max] (clamped, >=0).

    Replaces "always aim for max": with 1..3 a human likes sometimes 1, sometimes 2,
    sometimes 3 — not 3 every time."""
    r = rng or random
    # max is the hard ceiling: an explicit max=0 means "no likes" (must not be
    # overridden by a default min=1); min is clamped DOWN to it if misconfigured.
    hi = max(0, int(max_likes))
    lo = min(max(0, int(min_likes)), hi)
    return r.randint(lo, hi)


def sample_story_like_slot(max_slides: int, *, rng=None) -> int:
    """Pick the single story slide (0-based) to like, when a story-like is planned.

    A human who likes a story likes ONE slide that resonates — never all of them. Returns a
    varied index in [0, max_slides-1]; the caller likes at most that one slide (with a
    last-slide fallback if the real story is shorter than the sampled index)."""
    r = rng or random
    n = max(1, int(max_slides))
    return r.randint(0, n - 1)


def build_interaction_plan(config: dict, interactions_to_do, *, rng=None) -> InteractionPlan:
    """Resolve a per-profile `InteractionPlan` from the action config + the rolled
    `interactions_to_do` list (['like','follow','comment','story','story_like']).

    `interactions_to_do` carries the probability rolls (which intents fire for this profile);
    this function turns the "yes" intents into concrete quantities (sampled like target, the
    single story-like slot). Quantities come from `min/max_likes_per_profile` and
    `max_stories_per_profile`; the gesture execution stays in the engine."""
    intents = set(interactions_to_do or [])
    do_like = 'like' in intents
    do_watch = ('story' in intents) or ('story_like' in intents)
    do_story_like = 'story_like' in intents

    min_likes = config.get('min_likes_per_profile', 1)
    max_likes = config.get('max_likes_per_profile', 3)
    max_slides = config.get('max_stories_per_profile', 3)

    like_target = sample_like_target(min_likes, max_likes, rng=rng) if do_like else 0
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
    "sample_like_target",
    "sample_story_like_slot",
    "build_interaction_plan",
]
