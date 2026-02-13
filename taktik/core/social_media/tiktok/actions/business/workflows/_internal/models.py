"""Shared data models for TikTok video-based workflows."""

from typing import Dict, Any
from dataclasses import dataclass, field
import time


@dataclass
class VideoWorkflowStats:
    """Statistics shared by all video-based workflows (ForYou, Search, …)."""

    videos_watched: int = 0
    videos_liked: int = 0
    users_followed: int = 0
    videos_favorited: int = 0
    videos_skipped: int = 0
    ads_skipped: int = 0
    popups_closed: int = 0
    suggestions_handled: int = 0
    errors: int = 0

    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            'videos_watched': self.videos_watched,
            'videos_liked': self.videos_liked,
            'users_followed': self.users_followed,
            'videos_favorited': self.videos_favorited,
            'videos_skipped': self.videos_skipped,
            'ads_skipped': self.ads_skipped,
            'popups_closed': self.popups_closed,
            'suggestions_handled': self.suggestions_handled,
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }
