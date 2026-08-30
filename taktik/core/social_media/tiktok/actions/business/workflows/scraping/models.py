"""Data models for the TikTok Scraping workflow."""

from typing import List, Dict, Any
from dataclasses import dataclass, field
import time


@dataclass
class ScrapingConfig:
    """Configuration for the TikTok scraping workflow."""
    scrape_type: str = 'target'           # 'target', 'hashtag', 'post_url' or 'sound'
    target_usernames: List[str] = field(default_factory=list)
    target_scrape_type: str = 'followers'  # 'followers' or 'following'
    hashtag: str = ''
    #: Post links to harvest commenters from. On TikTok the people who LIKED a post are not
    #: rendered anywhere, so the audience signal a post carries is its commenters.
    post_urls: List[str] = field(default_factory=list)
    #: How many commenters to identify per post. Each one costs a profile round trip (~13s),
    #: because a comment row carries a display name and no handle at all.
    max_commenters_per_post: int = 20
    #: Sound mode. A sound is a targeting source TikTok has and Instagram does not: everyone
    #: riding one trend, which is a sharper audience than everyone who typed one word.
    #: The floor exists because most sounds are somebody's own original audio with three posts --
    #: opening those costs twenty seconds and returns their author, whom we already had.
    min_sound_posts: int = 500
    max_users_per_sound: int = 10
    max_sounds_per_session: int = 5
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
