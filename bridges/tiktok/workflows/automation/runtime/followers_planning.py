"""Planning helpers for the TikTok Followers bridge runner."""

from typing import Any, Dict, List, Tuple


def build_target_list(config: Dict[str, Any]) -> List[str]:
    """Return normalized target usernames from current and legacy payload fields."""
    target_accounts = config.get("targetAccounts", [])
    targets = config.get("targets", [])
    search_query = config.get("searchQuery")

    if target_accounts and len(target_accounts) > 0:
        return [target.strip().replace("@", "") for target in target_accounts if target.strip()]
    if targets and len(targets) > 0:
        return [target.strip().replace("@", "") for target in targets if target.strip()]
    if search_query:
        return [search_query.strip().replace("@", "")]
    return []


def has_empty_target_candidates(config: Dict[str, Any]) -> bool:
    """Return True when target arrays were provided but normalized to no username."""
    return bool(config.get("targetAccounts")) or bool(config.get("targets"))


def calculate_target_distribution(config: Dict[str, Any], target_count: int) -> Tuple[int, int, int]:
    """Return total, base profiles per target and extra profiles for first targets."""
    max_followers_total = config.get("maxFollowers") or config.get("maxVideos", 20)
    profiles_per_target = max(1, max_followers_total // target_count)
    extra_profiles = max_followers_total % target_count
    return max_followers_total, profiles_per_target, extra_profiles


def max_profiles_for_target(target_idx: int, profiles_per_target: int, extra_profiles: int) -> int:
    """Distribute extra profile budget to the first targets."""
    return profiles_per_target + (1 if target_idx < extra_profiles else 0)


def build_followers_config(
    followers_config_class,
    config: Dict[str, Any],
    current_target: str,
    target_max_followers: int,
    remaining_likes: int,
    remaining_follows: int,
):
    """Build the core FollowersConfig from the bridge payload and session limits."""
    return followers_config_class(
        search_query=current_target,
        max_followers=target_max_followers,
        posts_per_profile=config.get("postsPerProfile", 2),
        min_watch_time=config.get("minWatchTime", 5.0),
        max_watch_time=config.get("maxWatchTime", 15.0),
        like_probability=config.get("likeProbability", 70) / 100.0,
        favorite_probability=config.get("favoriteProbability", 30) / 100.0,
        follow_probability=config.get("followProbability", 50) / 100.0,
        story_like_probability=config.get("storyLikeProbability", 50) / 100.0,
        max_likes_per_session=remaining_likes,
        max_follows_per_session=remaining_follows,
        min_delay=config.get("minDelay", 1.0),
        max_delay=config.get("maxDelay", 3.0),
        pause_after_actions=config.get("pauseAfterActions", 10),
        pause_duration_min=config.get("pauseDurationMin", 30.0),
        pause_duration_max=config.get("pauseDurationMax", 60.0),
        include_friends=config.get("includeFriends", False),
        max_consecutive_known_usernames=config.get("maxConsecutiveKnownUsernames", 150),
    )


def should_stop_after_target(completion_reason: str) -> bool:
    """Return True when a target completion reason should stop the multi-target run."""
    return completion_reason in {
        "max_likes_reached",
        "max_follows_reached",
        "stopped_by_user",
        "navigation_failed",
        "ERROR",
    }
