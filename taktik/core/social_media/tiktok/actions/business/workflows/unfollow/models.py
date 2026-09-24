"""Data models for the TikTok Unfollow workflow."""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class UnfollowConfig:
    """Configuration for the Unfollow workflow."""
    max_unfollows: int = 20
    include_friends: bool = False
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_scroll_attempts: int = 10
    #: Keep an account the bot followed less than this many days ago; 0 = no age rule. The
    #: scheduler node has offered "Âge min. (jours)" all along and nothing read it until
    #: 2026-09-24. The age comes from the bot's own FOLLOW interactions: an account with no such
    #: record (followed by hand, or before the base existed) has no known age and is not held back.
    min_follow_age_days: int = 0
    #: The acting account, to look its follows up. Without it the age rule cannot apply.
    bot_username: Optional[str] = None


@dataclass
class UnfollowStats:
    """Stats for the Unfollow workflow."""
    unfollowed: int = 0
    skipped_friends: int = 0
    skipped_recent_follows: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unfollowed": self.unfollowed,
            "skipped_friends": self.skipped_friends,
            "skipped_recent_follows": self.skipped_recent_follows,
            "errors": self.errors,
        }
