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
    #   'likers'     — open ONE post and walk the people who liked it (historical default)
    #   'commenters' — same post, but the people who took the time to WRITE something: a
    #                  stronger signal, and the same downstream loop (shared list source).
    #   'posts'      — no people list at all: like/comment the POSTS themselves, one after
    #                  another, the way the Feed workflow engages your own feed.
    # In 'posts' mode `max_interactions` counts POSTS, not profiles — there is no profile.
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
    # ACQUISITION from the feed, off by default. The feed workflow long engaged only OUR
    # own feed, never visiting a profile, so these three keys sat in the catalog without
    # any code reading them. They act now:
    #   visit the post author and interact — that is where the relationship filters
    #     `follow_percentage` et `story_watch_percentage` prennent enfin un sens : un post
    #     become meaningful, since a feed post carries neither
    #   open the post likers and walk them
    #   do not engage the reels of the feed
    # As soon as either of the first two is active, the RELATIONSHIP filters become
    # pertinents : il y a alors une vraie decision d'acquisition a gater.
    'interact_with_post_author': False,
    'interact_with_post_likers': False,
    'max_likers_per_post': 5,
    'skip_reels': False,
    'skip_ads': True,
    # Human crawl (browse_feed/scroll_feed_to_next_post) toggles — default ON so the
    # feed workflow scrolls like a human (skip suggestions, read captions, browse carousels).
    # Exposed as future per-account bot settings.
    'skip_suggested': True,
    'read_captions': True,
    'browse_carousels': True,
    'like_posts_directly': True,
    # Collection of the ADS crossed during the run, off by default. The crawl already
    # recognises the sponsored posts in order to avoid them; when enabled it captures
    # them in passing instead of throwing that recognition away. No ad is ever opened:
    # tapping one would signal interest to the ranking, and adds nothing to the
    # reading that matters.
    'capture_ads': False,
    'min_post_likes': 0,
    'max_post_likes': 0,
    # --- Suggestions-follow mode, off by default ---
    # When the suggestions carousel appears in the feed, open its CTA and follow in
    # bulk from the discovery screen. Does NEITHER follow-back NOR follow-request
    # acceptance, both of which belong to the notifications workflow.
    'follow_suggestions': False,
    # Suggestions-only run: the feed is only a corridor to the carousel. No like,
    # ni commentaire, ni story — on scrolle jusqu'au bloc, on follow, on s'arrete.
    'suggestions_only': False,
    'max_carousel_scrolls': 12,
    'max_suggestion_follows': 20,
    # Deny, the default, refuses the address-book access; allow grants it.
    'suggestions_contacts_choice': 'deny',
    'suggestion_follow_delay_range': (4, 12),
    'max_suggestion_scrolls': 15,
    # Suggestion passes allowed within one feed run.
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
