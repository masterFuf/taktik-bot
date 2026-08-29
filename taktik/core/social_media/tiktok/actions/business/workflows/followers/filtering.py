"""Profile filtering for the TikTok Followers workflow.

TikTok filtered nothing: every follower listed was visited and interacted with, whatever its
size, its bio or its emptiness. The evaluator itself already existed -- written for Instagram,
depending on nothing but data -- and now lives in `shared/filtering`, which is what this module
calls.

Two adaptations are needed, and both are about vocabulary rather than logic.

TikTok counts *videos* where the evaluator reads `posts_count`, and shows a *display name* where
it reads `full_name`. Feeding it TikTok's own field names would not raise anything: it would read
zeros, hand every profile the "Very low posting activity" and "No visible posts" penalties, and
quietly cost 35 points to profiles that deserve none of it.

The criteria arrive in the app's camelCase and are read in snake_case. Instagram converts them in
its config builder, applying its own defaults on the way (min 50 followers, min 5 posts). Those
defaults are NOT reproduced here: TikTok filtering ships disabled, so an absent criterion means no
constraint, and a run whose config says nothing about filters behaves exactly as it did before.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from taktik.core.shared.config import resolve_filter_criteria
from taktik.core.shared.filtering import apply_comprehensive_filter


#: camelCase name sent by the app -> snake_case name read by the evaluator. Only the criteria the
#: evaluator actually reads are listed; anything already in snake_case passes straight through.
_CRITERIA_ALIASES = {
    "minFollowers": "min_followers",
    "maxFollowers": "max_followers",
    "minPosts": "min_posts",
    "minVideos": "min_posts",
    "allowPrivate": "allow_private",
    "maxFollowingRatio": "max_following_ratio",
    "verifiedPenalty": "verified_penalty",
    "businessPenalty": "business_penalty",
    "forbiddenBioKeywords": "forbidden_bio_keywords",
    "requiredBioKeywords": "required_bio_keywords",
    "requireBio": "require_bio",
    "requireFullName": "require_full_name",
    "requireDisplayName": "require_full_name",
    "minScore": "min_score",
}

#: Handled apart from the aliases: this one is inverted, not renamed.
_SKIP_PRIVATE_KEYS = ("skipPrivateAccounts", "skip_private_accounts")


def resolve_tiktok_filter_criteria(config: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Read the filter criteria out of a TikTok workflow config, in either casing.

    Empty in, empty out -- and an empty criteria dict rejects nobody, which is how TikTok
    filtering ships.
    """
    resolved = resolve_filter_criteria(config)
    if not resolved:
        return {}

    criteria: Dict[str, Any] = {}
    for key, value in resolved.items():
        if value is None or value == "":
            continue
        if key in _SKIP_PRIVATE_KEYS:
            # Not a rename but an inversion, and the reason this knob existed for months
            # without doing anything: `skip_private_accounts` was parsed by the handler,
            # stored on the config and read by nobody. Only the True case speaks -- a False
            # here means "not asked", not "let private accounts through", which is the
            # evaluator's own default anyway.
            if value:
                criteria["allow_private"] = False
            continue
        criteria[_CRITERIA_ALIASES.get(key, key)] = value
    return criteria


def tiktok_profile_for_filtering(
    profile_data: Mapping[str, Any], *, visible_posts_count: Optional[int] = None
) -> Dict[str, Any]:
    """Translate an extracted TikTok profile into the evaluator's vocabulary."""
    videos = profile_data.get("videos_count") or 0
    return {
        "username": profile_data.get("username", "unknown"),
        "followers_count": profile_data.get("followers_count") or 0,
        "following_count": profile_data.get("following_count") or 0,
        "posts_count": videos,
        "biography": profile_data.get("biography") or profile_data.get("bio") or "",
        "full_name": profile_data.get("display_name") or "",
        "is_private": bool(profile_data.get("is_private", False)),
        "is_verified": bool(profile_data.get("is_verified", False)),
        # TikTok exposes no business flag on a profile screen. Left absent rather than guessed:
        # a False that means "not read" would be indistinguishable from one that means "not a
        # business", and only the second should ever escape a penalty.
        "visible_posts_count": videos if visible_posts_count is None else visible_posts_count,
    }


def evaluate_tiktok_profile(
    profile_data: Mapping[str, Any],
    criteria: Mapping[str, Any],
    *,
    visible_posts_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Score an extracted TikTok profile. Returns the evaluator's verdict unchanged."""
    if not criteria:
        return {"suitable": True, "score": 100, "reasons": [], "category": "suitable",
                "filter_details": {}, "username": profile_data.get("username", "unknown")}

    return apply_comprehensive_filter(
        tiktok_profile_for_filtering(profile_data, visible_posts_count=visible_posts_count),
        criteria,
    )


__all__ = [
    "evaluate_tiktok_profile",
    "resolve_tiktok_filter_criteria",
    "tiktok_profile_for_filtering",
]
