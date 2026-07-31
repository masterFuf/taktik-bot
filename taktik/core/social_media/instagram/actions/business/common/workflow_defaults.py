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
    'story_like_probability': 0.0,
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
    # WHAT the run engages, from the same hashtag search:
    #   'likers' — open ONE post and walk the people who liked it (historical default)
    #   'posts'  — no people list at all: like/comment the POSTS themselves, one after
    #              another, the way the Feed workflow engages your own feed.
    # In 'posts' mode `max_interactions` counts POSTS, not profiles — there is no profile.
    # (A 'commenters' source exists for the post_url workflow; the hashtag flow has never
    # had it, so it is not offered here rather than being half-wired.)
    'interaction_mode': 'likers',
}


# ─── Post URL workflow ───────────────────────────────────────────────────────

POST_URL_DEFAULTS: Dict[str, Any] = {
    **_INTERACTION_DEFAULTS,
    'like_percentage': 70,
    'min_likes_per_profile': 2,
    # Which population of the post we walk: 'likers' (the bottom-sheet) or 'commenters'
    # (the thread — people who took the time to write something, a stronger signal).
    'source_mode': 'likers',
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
    'view_feed_stories': False,
    'max_feed_story_profiles': 5,
    'feed_story_reaction_percentage': 0,
    'feed_story_reaction': 'laugh',
    'interact_with_post_author': False,
    'interact_with_post_likers': False,
    'skip_reels': False,
    'skip_ads': True,
    # Human crawl (browse_feed/scroll_feed_to_next_post) toggles — default ON so the
    # feed workflow scrolls like a human (skip suggestions, read captions, browse carousels).
    # Exposed as future per-account bot settings.
    'skip_suggested': True,
    'read_captions': True,
    'browse_carousels': True,
    'like_posts_directly': True,
    'min_post_likes': 0,
    'max_post_likes': 0,
    # --- Mode "follow des suggestions" (OFF par defaut) ---
    # Quand le carousel "Suggested for you" apparait dans le feed, ouvrir son CTA
    # "See all" et follow en masse depuis l'ecran Discover people. Ne fait NI
    # follow-back NI acceptation de demande de suivi (workflow Notifications).
    'follow_suggestions': False,
    # Run "suggestions seules" : le feed n'est qu'un couloir vers le carousel. Ni like,
    # ni commentaire, ni story — on scrolle jusqu'au bloc, on follow, on s'arrete.
    'suggestions_only': False,
    'max_carousel_scrolls': 12,
    'max_suggestion_follows': 20,
    # 'deny' (defaut) = refuser l'acces au carnet d'adresses ; 'allow' = l'accorder.
    'suggestions_contacts_choice': 'deny',
    'suggestion_follow_delay_range': (4, 12),
    'max_suggestion_scrolls': 15,
    # Nombre de passes de suggestions autorisees dans un meme run de feed.
    'max_suggestion_passes': 1,
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
    'unfollow_mode': 'non-followers',  # 'non-followers' | 'mutual' | 'oldest' | 'all'
    'unfollow_non_followers': True,  # Legacy compat — prefer unfollow_mode
    'min_days_since_follow': 3,
    'skip_verified': True,
    'skip_business': False,
    'bot_follows_only': False,
    'whitelist': [],
    'blacklist': [],
}
