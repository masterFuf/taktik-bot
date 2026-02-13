"""Data models for the TikTok Unfollow workflow."""

from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class UnfollowConfig:
    """Configuration for the Unfollow workflow."""
    max_unfollows: int = 20
    include_friends: bool = False
    min_delay: float = 1.0
    max_delay: float = 3.0
    max_scroll_attempts: int = 10


@dataclass
class UnfollowStats:
    """Stats for the Unfollow workflow."""
    unfollowed: int = 0
    skipped_friends: int = 0
    errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unfollowed": self.unfollowed,
            "skipped_friends": self.skipped_friends,
            "errors": self.errors,
        }
