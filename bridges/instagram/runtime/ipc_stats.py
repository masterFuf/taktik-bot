"""Stats IPC helpers for Instagram bridge runtime."""

from __future__ import annotations

from bridges.common.runtime.bridge_base import _ipc, logger


def send_stats(likes: int = 0, follows: int = 0, comments: int = 0, profiles: int = 0, unfollows: int = 0):
    """Send legacy stats update to desktop app."""
    _ipc.send("stats", likes=likes, follows=follows, comments=comments, profiles=profiles, unfollows=unfollows)


def send_instagram_stats(
    profiles_visited: int = 0,
    profiles_interacted: int = 0,
    profiles_filtered: int = 0,
    private_profiles: int = 0,
    likes: int = 0,
    follows: int = 0,
    comments: int = 0,
    stories_watched: int = 0,
    errors: int = 0,
):
    """Send comprehensive Instagram stats update to desktop app."""
    _ipc.instagram_stats(
        profiles_visited=profiles_visited,
        profiles_interacted=profiles_interacted,
        profiles_filtered=profiles_filtered,
        private_profiles=private_profiles,
        likes=likes,
        follows=follows,
        comments=comments,
        stories_watched=stories_watched,
        errors=errors,
    )


def _on_stats_update(stats_dict: dict):
    """Callback for BaseStatsManager to send stats via IPC."""
    send_instagram_stats(
        profiles_visited=stats_dict.get("profiles_visited", 0),
        profiles_interacted=stats_dict.get("profiles_interacted", 0),
        profiles_filtered=stats_dict.get("profiles_filtered", 0),
        private_profiles=stats_dict.get("private_profiles", 0),
        likes=stats_dict.get("likes", 0),
        follows=stats_dict.get("follows", 0),
        comments=stats_dict.get("comments", 0),
        stories_watched=stats_dict.get("stories_watched", 0),
        errors=stats_dict.get("errors", 0),
    )


def setup_stats_callback():
    """Setup the stats callback on BaseStatsManager for IPC updates."""
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager

        original_init = BaseStatsManager.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            self.set_on_stats_callback(_on_stats_update)

        BaseStatsManager.__init__ = patched_init
        logger.info("\u2705 Stats IPC callback configured for BaseStatsManager")
    except Exception as e:
        logger.warning(f"Could not setup stats callback: {e}")
