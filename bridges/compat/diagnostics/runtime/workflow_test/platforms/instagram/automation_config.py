"""Instagram automation config builder for compat workflow diagnostics."""

import math


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
) -> dict:
    """Build a workflow config matching the format expected by InstagramAutomation.

    When ``filters`` is provided (mirroring the real workflow's profile-filter
    card) it is honoured verbatim, so a test run applies the exact same profile
    selection as production instead of a permissive stub.

    Mirroring the real config surface (Lot 4): when ``delays`` is None the run is
    rhythm-driven, so ``delay_between_actions`` is omitted and the SessionManager
    derives the pace from ``behavior_policy`` (the pacing profile). When ``delays``
    is provided it wins for back-compat, exactly like the production path.
    """
    max_profiles = limits.get("maxProfiles", 3)
    min_likes = limits.get("minLikesPerProfile", 1)
    max_likes = limits.get("maxLikesPerProfile", 1)
    like_pct = probs.get("like", 80)
    follow_pct = probs.get("follow", 0)
    comment_pct = probs.get("comment", 0)
    story_pct = probs.get("watchStories", 0)
    story_like_pct = probs.get("likeStories", 0)

    action_type, interaction_type, session_wf_type = _resolve_workflow_types(workflow_type)
    target_list = [value.strip() for value in target.split(",") if value.strip()]

    action_config = {
        "type": action_type,
        "target_username": target_list[0] if target_list else target,
        "target_usernames": target_list,
        "hashtag": target if action_type == "hashtag" else None,
        "interaction_type": interaction_type,
        "max_interactions": max_profiles,
        "like_posts": True,
        "min_likes_per_profile": min_likes,
        "max_likes_per_profile": max_likes,
        "probabilities": {
            "like_percentage": like_pct,
            "follow_percentage": follow_pct,
            "comment_percentage": comment_pct,
            "story_percentage": story_pct,
            "story_like_percentage": story_like_pct,
        },
        "like_settings": {"enabled": like_pct > 0, "like_carousels": True, "like_reels": True},
        "follow_settings": {"enabled": follow_pct > 0},
        "story_settings": {"enabled": story_pct > 0},
        "story_like_settings": {"enabled": story_like_pct > 0},
        "comment_settings": {"enabled": comment_pct > 0, "custom_comments": []},
    }

    if action_type == "feed":
        action_config = {
            "type": "feed",
            "max_interactions": max_profiles,
            "like_percentage": like_pct,
            "follow_percentage": follow_pct,
            "comment_percentage": comment_pct,
            "story_watch_percentage": story_pct,
        }
    elif action_type == "notifications":
        action_config = {
            "type": "notifications",
            "max_interactions": limits.get("maxInteractions", max_profiles),
            "like_percentage": like_pct,
            "follow_percentage": follow_pct,
            "comment_percentage": comment_pct,
        }
    elif action_type == "unfollow":
        action_config = {
            "type": "unfollow",
            "max_unfollows": limits.get("maxUnfollows", 10),
            "unfollow_mode": "non_followers",
            "skip_verified": False,
            "skip_business": False,
        }
    elif action_type == "post_url":
        action_config["type"] = "post_url"
        action_config["post_url"] = target

    f = filters or {}
    allow_private = f.get("allowPrivate", True)
    filters_config = {
        "min_followers": f.get("minFollowers", 0),
        "max_followers": f.get("maxFollowers", 999999999),
        "min_followings": 0,
        "max_followings": f.get("maxFollowing", 999999999),
        "min_posts": f.get("minPosts", 0),
        "privacy_relation": "public_and_private" if allow_private else "public",
        # Real workflows read these allow_* flags from the filter criteria.
        "allow_private": allow_private,
        "allow_verified": f.get("allowVerified", True),
        "allow_business": f.get("allowBusiness", True),
        "blacklist_words": [],
    }

    session_settings = {
        "workflow_type": session_wf_type,
        "total_profiles_limit": max_profiles,
        "total_follows_limit": math.ceil(max_profiles * follow_pct / 100) if follow_pct else 0,
        "total_likes_limit": math.ceil(max_profiles * max_likes * like_pct / 100) if like_pct else 0,
        "session_duration_minutes": session_duration,
        "randomize_actions": False,
    }
    # Explicit delays win for back-compat; absent => the pacing profile drives the rhythm.
    if delays:
        session_settings["delay_between_actions"] = delays
    if max_consecutive_known is not None:
        session_settings["max_consecutive_known_usernames"] = max_consecutive_known

    config = {
        "filters": filters_config,
        "session_settings": session_settings,
        "actions": [action_config],
    }
    # Top-level behaviorPolicy mirrors the production config: SessionManager reads it to
    # resolve the pacing profile (taktik/core/shared/behavior/profiles.py).
    if behavior_policy:
        config["behaviorPolicy"] = behavior_policy
    return config


def _resolve_workflow_types(workflow_type: str) -> tuple[str, str, str]:
    if workflow_type in ("target_followers", "target_following"):
        interaction_type = "followers" if workflow_type == "target_followers" else "following"
        return "interact_with_followers", interaction_type, "target_followers"
    if workflow_type == "hashtag":
        return "hashtag", "hashtag", "hashtag"
    if workflow_type in ("post_likers", "post_url"):
        return "post_url", "post_likers", "post_url"
    if workflow_type == "feed":
        return "feed", "feed", "feed"
    if workflow_type == "notifications":
        return "notifications", "notifications", "notifications"
    if workflow_type == "unfollow":
        return "unfollow", "unfollow", "unfollow"
    return "interact_with_followers", "followers", "target_followers"


__all__ = ["build_workflow_config"]
