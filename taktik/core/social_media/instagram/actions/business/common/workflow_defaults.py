"""Centralized default configurations for all Instagram automation workflows.

Each workflow has its own defaults dict that merges shared interaction defaults
with workflow-specific settings. This avoids duplicating the same config keys
across 6+ workflow files.

Usage in a workflow:
    from ..common.workflow_defaults import FOLLOWERS_DEFAULTS
    self.default_config = {**FOLLOWERS_DEFAULTS}
"""

from typing import Dict, Any


# ─── Shared interaction defaults ─────────────────────────────────────────────
# Common to all workflows that visit profiles and interact (like, follow, etc.)

_INTERACTION_DEFAULTS: Dict[str, Any] = {
    'max_interactions': 20,
    'interaction_delay_range': (20, 40),
    'like_percentage': 80,
    'follow_percentage': 15,
    'comment_percentage': 5,
    'story_watch_percentage': 10,
    'story_like_percentage': 0,
    'max_likes_per_profile': 3,
    'max_comments_per_profile': 1,
    'max_stories_per_profile': 3,
}


# ─── Followers workflow ──────────────────────────────────────────────────────

FOLLOWERS_DEFAULTS: Dict[str, Any] = {
    'max_followers_to_extract': 50,
    'max_interactions_per_session': 20,
    'interaction_delay_range': (5, 12),
    'scroll_attempts': 5,
    # Followers uses probability format (0.0-1.0) instead of percentage (0-100)
    'like_probability': 0.8,
    'follow_probability': 0.2,
    'story_probability': 0.15,
    'comment_probability': 0.05,
    'like_posts': True,
    'max_likes_per_profile': 4,
}


# ─── Hashtag workflow ────────────────────────────────────────────────────────

HASHTAG_DEFAULTS: Dict[str, Any] = {
    **_INTERACTION_DEFAULTS,
    'max_posts_to_analyze': 20,
    'min_likes': 100,
    'max_likes': 50000,
    'max_interactions': 30,
    'max_likes_per_profile': 2,
}


# ─── Post URL workflow ───────────────────────────────────────────────────────

POST_URL_DEFAULTS: Dict[str, Any] = {
    **_INTERACTION_DEFAULTS,
    'like_percentage': 70,
    'min_likes_per_profile': 2,
}


# ─── Feed workflow ───────────────────────────────────────────────────────────

FEED_DEFAULTS: Dict[str, Any] = {
    **_INTERACTION_DEFAULTS,
    'max_posts_to_check': 30,
    'interaction_delay_range': (2, 5),
    'like_percentage': 100,
    'follow_percentage': 0,
    'comment_percentage': 0,
    'story_watch_percentage': 0,
    'interact_with_post_author': False,
    'interact_with_post_likers': False,
    'skip_reels': False,
    'skip_ads': True,
    'like_posts_directly': True,
    'min_post_likes': 0,
    'max_post_likes': 0,
}


# ─── Notifications workflow ──────────────────────────────────────────────────

NOTIFICATIONS_DEFAULTS: Dict[str, Any] = {
    **_INTERACTION_DEFAULTS,
    'like_percentage': 70,
    'notification_types': ['likes', 'follows', 'comments'],
}


# ─── Unfollow workflow ───────────────────────────────────────────────────────

UNFOLLOW_DEFAULTS: Dict[str, Any] = {
    'max_unfollows': 20,
    'unfollow_delay_range': (30, 60),
    'unfollow_non_followers': True,
    'min_days_since_follow': 3,
    'skip_verified': True,
    'skip_business': False,
}
