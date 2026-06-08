"""Instagram live interaction IPC events."""

from __future__ import annotations

from bridges.common.runtime.bridge_base import _ipc


def send_instagram_action(action: str, username: str, details: dict = None):
    """Send Instagram action event to desktop app."""
    _ipc.instagram_action(action, username, details)


def send_instagram_profile_visit(username: str, followers: int = None, is_private: bool = False):
    """Send profile visit event to desktop app."""
    _ipc.profile_visit(username, followers, is_private)


def send_unfollow_event(username: str, success: bool = True):
    """Send unfollow event to desktop app for real-time activity."""
    _ipc.unfollow_event(username, success)


def send_follow_event(username: str, success: bool = True, profile_data: dict = None):
    """Send follow event to desktop app for real-time activity and WorkflowAnalyzer."""
    _ipc.follow_event(username, success, profile_data)


def send_like_event(username: str, likes_count: int = 1, profile_data: dict = None):
    """Send like event to desktop app for real-time activity and WorkflowAnalyzer."""
    _ipc.like_event(username, likes_count, profile_data)


def send_story_event(username: str, stories_watched: int = 1, stories_liked: int = 0,
                     profile_data: dict = None):
    """Send story watch/like event to desktop app for real-time activity and WorkflowAnalyzer."""
    _ipc.story_event(username, stories_watched, stories_liked, profile_data)


def send_feed_decision(author: str, action: str, reason: str = None,
                       comment: str = None, visit_profile: bool = False):
    """Send a per-post feed decision (classic feed workflow) as an agent_decision
    event so the desktop renders it as a Taktik Agent feed card.

    action is 'like' | 'like_comment' | 'skip'. Reuses the AI autopilot's
    agent_decision wire event (the front already maps it to a feed_decision card);
    the classic feed is rule-based so no model/cost is attached.
    """
    _ipc.agent_decision(
        action=action, author=author, reason=reason,
        comment=comment, visit_profile=visit_profile,
    )


__all__ = [
    "send_instagram_action",
    "send_instagram_profile_visit",
    "send_unfollow_event",
    "send_follow_event",
    "send_like_event",
    "send_story_event",
    "send_feed_decision",
]
