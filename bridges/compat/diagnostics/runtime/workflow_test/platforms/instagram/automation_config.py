"""Instagram automation config for compat workflow diagnostics.

The bench does NOT build this config itself any more. It assembles the same camelCase payload
the desktop bridge sends and hands it to the PRODUCTION builder.

It used to keep a parallel builder, and every setting added to a workflow page had to be
re-declared here. None ever was, so the bench quietly drifted behind production:

  - a feed run carried none of the acquisition options (`interactWithPostAuthor`,
    `interactWithPostLikers`, `maxLikersPerPost`, `skipReels`) — it scrolled and liked, and
    never visited an author or opened a post's likers;
  - a hashtag run carried none of the plan keys, so `resolve_interaction_plan` fell through
    to the legacy exclusive mode. The bench validated ONE post and its likers — a shape the
    production page no longer emits.

A green run on a divergent config proves nothing about production, which is the one thing
this bench exists to do.
"""

from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)


# Bench workflow value -> the vocabulary the production builder speaks. Explicit rather than a
# pass-through because that builder fails loudly on an unknown type instead of guessing, and
# because the two vocabularies genuinely differ (`hashtag` here, `hashtags` there).
_PROD_WORKFLOW_TYPES = {
    "target_followers": "target_followers",
    "target_following": "target_following",
    "hashtag": "hashtags",
    "post_likers": "post_url",
    "post_url": "post_url",
    "feed": "feed",
    "unfollow": "unfollow",
}


def build_workflow_config(
    workflow_type: str,
    target: str,
    limits: dict,
    probs: dict,
    session_duration: int = 30,
    delays: dict | None = None,
    filters: dict | None = None,
    max_consecutive_known: int | None = None,
    behavior_policy: dict | None = None,
    options: dict | None = None,
) -> dict:
    """Build the workflow config for a bench run, through the production builder.

    ``options`` carries the page-level settings verbatim (`engagePosts`, `walkLikers`,
    `feed: {...}`, …). It is deliberately opaque here: the production builder owns their
    whitelist, so a NEW page setting reaches the bench without touching this file — which is
    the whole point of delegating.
    """
    prod_type = _PROD_WORKFLOW_TYPES.get(workflow_type)
    if prod_type is None:
        return _notifications_config(workflow_type, limits, probs, session_duration, filters)

    raw_config: dict = {
        "target": target,
        "workflowType": prod_type,
        "limits": {
            "maxProfiles": limits.get("maxProfiles", 3),
            "minLikesPerProfile": limits.get("minLikesPerProfile", 1),
            "maxLikesPerProfile": limits.get("maxLikesPerProfile", 1),
        },
        "probabilities": {
            "like": probs.get("like", 80),
            "follow": probs.get("follow", 0),
            "comment": probs.get("comment", 0),
            "watchStories": probs.get("watchStories", 0),
            "likeStories": probs.get("likeStories", 0),
        },
        # The bench's filter card is permissive by default where production is restrictive;
        # seeding the keys keeps the bench's own defaults instead of inheriting the other set.
        "filters": _filters_payload(filters or {}),
        "session": _session_payload(session_duration, delays, max_consecutive_known),
    }
    if behavior_policy:
        raw_config["behaviorPolicy"] = behavior_policy
    for key, value in (options or {}).items():
        raw_config[key] = value
    if prod_type == "hashtags":
        _seed_legacy_hashtag_plan(raw_config, raw_config["limits"]["maxProfiles"])

    built = build_instagram_automation_config(raw_config)
    _apply_bench_profile_filters(built, filters or {})
    return built


def _seed_legacy_hashtag_plan(raw_config: dict, max_interactions: int) -> None:
    """Give a caller that states no plan the bench's historical hashtag behaviour.

    The production builder always WRITES the three plan keys, even as ``None``, and
    ``resolve_interaction_plan`` keys off their PRESENCE — so an absent plan no longer falls
    through to the legacy mode, it yields a plan with all three false: a run that opens posts
    and engages nothing. The front always states a plan; this covers everyone else by
    reproducing what the legacy `likers` mode did — one post, its likers walked up to the
    interaction budget.
    """
    if any(key in raw_config for key in ("engagePosts", "walkLikers", "walkCommenters")):
        return
    raw_config["engagePosts"] = False
    raw_config["walkLikers"] = True
    raw_config["walkCommenters"] = False
    raw_config.setdefault("maxPosts", 1)
    raw_config.setdefault("maxLikersPerPost", max_interactions)


def _filters_payload(f: dict) -> dict:
    payload = dict(f)
    payload.setdefault("minFollowers", 0)
    payload.setdefault("maxFollowers", 999999999)
    payload.setdefault("minPosts", 0)
    payload.setdefault("maxFollowing", 999999999)
    return payload


def _session_payload(session_duration: int, delays: dict | None, max_consecutive_known: int | None) -> dict:
    payload: dict = {"durationMinutes": session_duration}
    # Explicit delays win for back-compat; absent => the pacing profile drives the rhythm,
    # exactly like the production path.
    if delays:
        payload["minDelay"] = delays.get("min")
        payload["maxDelay"] = delays.get("max")
    if max_consecutive_known is not None:
        payload["maxConsecutiveKnownUsernames"] = max_consecutive_known
    return payload


def _apply_bench_profile_filters(built: dict, f: dict) -> None:
    """Re-apply the bench's profile-filter card on top of the production filters.

    The production builder pins ``privacy_relation`` and emits no ``allow_*`` flags, so these
    three toggles would become decorative the moment the bench delegates. They stay local on
    purpose: the real pages send them too, so whether production should carry them is its own
    question — not something to settle as a side effect of this refactor.
    """
    allow_private = f.get("allowPrivate", True)
    built["filters"].update({
        "privacy_relation": "public_and_private" if allow_private else "public",
        "allow_private": allow_private,
        "allow_verified": f.get("allowVerified", True),
        "allow_business": f.get("allowBusiness", True),
    })


def _notifications_config(workflow_type: str, limits: dict, probs: dict, session_duration: int,
                          filters: dict | None) -> dict:
    """Local shape for `notifications`, which the production builder refuses by design.

    Reading the activity feed belongs to the notifications ENGAGEMENT bridge, which owns its
    own persistence and app lifecycle; `build_instagram_automation_config` raises rather than
    turn it into a follower run. The bench still lists it as a workflow, so it keeps a config
    of its own here instead of crashing on that guard.
    """
    if workflow_type != "notifications":
        raise ValueError(f"Unknown bench workflow type {workflow_type!r}")

    f = filters or {}
    max_interactions = limits.get("maxInteractions", limits.get("maxProfiles", 3))
    built = {
        # Consumed shape is snake_case, like the production builder's output — `_filters_payload`
        # above produces the camelCase INPUT and would not be read here.
        "filters": {
            "min_followers": f.get("minFollowers", 0),
            "max_followers": f.get("maxFollowers", 999999999),
            "min_followings": 0,
            "max_followings": f.get("maxFollowing", 999999999),
            "min_posts": f.get("minPosts", 0),
            "blacklist_words": [],
        },
        "session_settings": {
            "workflow_type": "notifications",
            "total_profiles_limit": max_interactions,
            "session_duration_minutes": session_duration,
            "randomize_actions": False,
        },
        "actions": [{
            "type": "notifications",
            "max_interactions": max_interactions,
            "like_percentage": probs.get("like", 80),
            "follow_percentage": probs.get("follow", 0),
            "comment_percentage": probs.get("comment", 0),
        }],
    }
    _apply_bench_profile_filters(built, filters or {})
    return built


__all__ = ["build_workflow_config"]
