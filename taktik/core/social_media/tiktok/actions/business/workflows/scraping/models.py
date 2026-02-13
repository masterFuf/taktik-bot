"""Data models for the TikTok Scraping workflow."""

from typing import List, Dict, Any
from dataclasses import dataclass, field
import time


@dataclass
class ScrapingConfig:
    """Configuration for the TikTok scraping workflow."""
    scrape_type: str = 'target'           # 'target' or 'hashtag'
    target_usernames: List[str] = field(default_factory=list)
    target_scrape_type: str = 'followers'  # 'followers' or 'following'
    hashtag: str = ''
    max_profiles: int = 500
    max_videos: int = 50
    enrich_profiles: bool = True
    max_profiles_to_enrich: int = 50


@dataclass
class ScrapingStats:
    """Stats for the TikTok scraping workflow."""
    profiles_scraped: int = 0
    profiles_enriched: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        elapsed = time.time() - self.start_time
        return {
            'profiles_scraped': self.profiles_scraped,
            'profiles_enriched': self.profiles_enriched,
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }


def empty_profile(username: str = '', display_name: str = '', is_enriched: bool = False) -> Dict[str, Any]:
    """Return a blank profile dict with standard keys."""
    return {
        'username': username,
        'display_name': display_name,
        'followers_count': 0,
        'following_count': 0,
        'likes_count': 0,
        'posts_count': 0,
        'bio': '',
        'website': '',
        'is_private': False,
        'is_verified': False,
        'is_enriched': is_enriched,
    }
