"""Config mapping for the TikTok For You bridge runner."""

from __future__ import annotations

from typing import Any, Dict


def build_for_you_config(for_you_config_class, config: Dict[str, Any]):
    """Build the core ForYouConfig from the bridge payload."""
    return for_you_config_class(
        max_videos=config.get("maxVideos", 50),
        min_watch_time=config.get("minWatchTime", 2.0),
        max_watch_time=config.get("maxWatchTime", 8.0),
        like_probability=config.get("likeProbability", 30) / 100.0,
        follow_probability=config.get("followProbability", 10) / 100.0,
        favorite_probability=config.get("favoriteProbability", 5) / 100.0,
        required_hashtags=config.get("requiredHashtags", []),
        excluded_hashtags=config.get("excludedHashtags", []),
        min_likes=config.get("minLikes"),
        max_likes=config.get("maxLikes"),
        max_likes_per_session=config.get("maxLikesPerSession", 50),
        max_follows_per_session=config.get("maxFollowsPerSession", 20),
        skip_already_liked=config.get("skipAlreadyLiked", True),
        skip_ads=config.get("skipAds", True),
        follow_back_suggestions=config.get("followBackSuggestions", False),
        pause_after_actions=config.get("pauseAfterActions", 10),
        pause_duration_min=config.get("pauseDurationMin", 30.0),
        pause_duration_max=config.get("pauseDurationMax", 60.0),
    )


__all__ = ["build_for_you_config"]
