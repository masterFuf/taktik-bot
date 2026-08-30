"""TikTok Search workflow config mapping."""

from typing import Any, Dict, Type


def build_search_config(
    search_config_class: Type[Any],
    config: Dict[str, Any],
    search_query: str,
    max_videos: int,
    remaining_likes: int,
    remaining_follows: int,
) -> Any:
    """Map a bridge payload and per-query limits to the core SearchConfig."""
    return search_config_class(
        search_query=search_query,
        max_videos=max_videos,
        min_watch_time=config.get("minWatchTime", 2.0),
        max_watch_time=config.get("maxWatchTime", 8.0),
        like_probability=config.get("likeProbability", 30) / 100.0,
        follow_probability=config.get("followProbability", 10) / 100.0,
        favorite_probability=config.get("favoriteProbability", 5) / 100.0,
        # Commenting reached this road on 2026-08-30. Absent from the payload it stays at zero,
        # so a run configured before it existed behaves exactly as it did.
        comment_probability=config.get("commentProbability", 0) / 100.0,
        max_comments_per_session=config.get("maxCommentsPerSession", 10),
        repost_probability=config.get("repostProbability", 0) / 100.0,
        max_reposts_per_session=config.get("maxRepostsPerSession", 5),
        comment_texts=config.get("commentTexts") or config.get("comments") or [],
        min_likes=config.get("minLikes"),
        max_likes=config.get("maxLikes"),
        max_likes_per_session=remaining_likes,
        max_follows_per_session=remaining_follows,
        skip_already_liked=config.get("skipAlreadyLiked", True),
        skip_ads=config.get("skipAds", True),
        pause_after_actions=config.get("pauseAfterActions", 10),
        pause_duration_min=config.get("pauseDurationMin", 30.0),
        pause_duration_max=config.get("pauseDurationMax", 60.0),
    )
