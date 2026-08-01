"""What a hashtag run does with each post it finds.

The three historical modes — walk the likers, walk the commenters, engage the posts — were
mutually exclusive, and they could not be combined because they were not three values of one
setting: `likers` opened ONE post and spent the run on its likers, while `posts` walked many
posts. Two different loops wearing one option.

The unifying model is that the POST is the unit: a run walks posts, and for each post it can
do any combination of three things. The old modes become special cases, every mix becomes
expressible, and the hashtag flow finally has the same shape as the feed one (which had
independent toggles from the start).

Budgets are per population and PER POST, because that is the sentence an operator actually
wants to write: "five likers and two commenters, on each post I open". A single shared
number could not say it, and that — not the checkbox — is what made mixing impossible.

Legacy configs keep working: a run that only names `interaction_mode` is translated here,
and the translation reproduces exactly what that mode did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

# What `max_interactions` meant in each legacy mode. It counted PROFILES for the two
# people-walking modes (from a single post) and POSTS for the third — the ambiguity this
# module exists to remove.
_LEGACY_MODES = ("likers", "commenters", "posts")

DEFAULT_MAX_POSTS = 1
DEFAULT_PER_POST = 20


@dataclass(frozen=True)
class InteractionPlan:
    """Resolved answer to "what do we do with each post of this hashtag?"."""

    engage_posts: bool
    walk_likers: bool
    walk_commenters: bool
    max_posts: int
    max_likers_per_post: int
    max_commenters_per_post: int
    #: The legacy mode this came from, or None when the plan was stated explicitly.
    legacy_mode: Optional[str] = None

    @property
    def visits_profiles(self) -> bool:
        """True when the run leaves the post to engage PEOPLE.

        False means the most discreet run we have: posts are liked/commented where they
        stand and no profile is ever opened — a warm-up alternative to the feed workflow.
        """
        return self.walk_likers or self.walk_commenters

    @property
    def is_noop(self) -> bool:
        return not (self.engage_posts or self.visits_profiles)

    def describe(self) -> str:
        """Short human summary, for logs and for the session record."""
        parts = []
        if self.engage_posts:
            parts.append("posts")
        if self.walk_likers:
            parts.append(f"likers×{self.max_likers_per_post}")
        if self.walk_commenters:
            parts.append(f"commenters×{self.max_commenters_per_post}")
        return f"{' + '.join(parts) or 'nothing'} over {self.max_posts} post(s)"

    def as_record(self) -> Dict[str, Any]:
        """Flat form, for storing on the session so the history says what actually ran."""
        return {
            "engage_posts": self.engage_posts,
            "walk_likers": self.walk_likers,
            "walk_commenters": self.walk_commenters,
            "max_posts": self.max_posts,
            "max_likers_per_post": self.max_likers_per_post,
            "max_commenters_per_post": self.max_commenters_per_post,
        }


def _positive(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def resolve_interaction_plan(config: Dict[str, Any]) -> InteractionPlan:
    """Read a hashtag config and say what each post is for.

    An explicit plan wins. Otherwise the legacy `interaction_mode` is translated, and the
    translation is deliberately literal — `likers` still means ONE post whose likers are
    walked up to `max_interactions`, because that is what it has always meant and a config
    saved last month must not start behaving differently.
    """
    stated = any(
        key in config
        for key in ("engage_posts", "walk_likers", "walk_commenters")
    )
    max_interactions = _positive(config.get("max_interactions"), DEFAULT_PER_POST)

    if stated:
        return InteractionPlan(
            engage_posts=bool(config.get("engage_posts", False)),
            walk_likers=bool(config.get("walk_likers", False)),
            walk_commenters=bool(config.get("walk_commenters", False)),
            max_posts=_positive(config.get("max_posts"), DEFAULT_MAX_POSTS),
            max_likers_per_post=_positive(config.get("max_likers_per_post"), DEFAULT_PER_POST),
            max_commenters_per_post=_positive(config.get("max_commenters_per_post"), DEFAULT_PER_POST),
        )

    mode = str(config.get("interaction_mode") or "likers").strip().lower()
    if mode not in _LEGACY_MODES:
        mode = "likers"

    if mode == "posts":
        # `max_interactions` counted POSTS here, and no profile was ever visited.
        return InteractionPlan(
            engage_posts=True, walk_likers=False, walk_commenters=False,
            max_posts=max_interactions,
            max_likers_per_post=DEFAULT_PER_POST,
            max_commenters_per_post=DEFAULT_PER_POST,
            legacy_mode=mode,
        )

    # `likers` / `commenters`: ONE post, and `max_interactions` people taken from it.
    return InteractionPlan(
        engage_posts=False,
        walk_likers=(mode == "likers"),
        walk_commenters=(mode == "commenters"),
        max_posts=DEFAULT_MAX_POSTS,
        max_likers_per_post=max_interactions,
        max_commenters_per_post=max_interactions,
        legacy_mode=mode,
    )


__all__ = ["InteractionPlan", "resolve_interaction_plan"]
