"""Data models for the Discovery workflow."""

from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum


class ScrapingPhase(Enum):
    """Phases du scraping d'un post."""
    PROFILE = "profile"
    LIKERS = "likers"
    COMMENTS = "comments"
    DONE = "done"


class SourceType(Enum):
    """Types de sources pour le discovery."""
    TARGET = "target"
    HASHTAG = "hashtag"
    POST_URL = "post_url"


@dataclass
class ProgressState:
    """État de progression pour une source."""
    source_type: str
    source_value: str
    current_phase: str = "profile"
    current_post_index: int = 0
    total_posts: int = 0
    likers_scraped: int = 0
    likers_total: int = 0
    comments_scraped: int = 0
    comments_total: int = 0
    profiles_enriched: int = 0
    last_scroll_position: dict = field(default_factory=dict)
    status: str = "in_progress"


@dataclass
class ScrapedProfile:
    """Profil scrapé avec toutes ses données."""
    username: str
    source_type: str
    source_value: str
    interaction_type: str = ""  # liker, commenter, target
    post_url: str = ""
    bio: str = ""
    website: str = ""
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    category: str = ""
    threads_username: str = ""
    comment_text: str = ""
    comment_likes: int = 0
    is_reply: bool = False


@dataclass
class ScrapedComment:
    """Commentaire scrapé avec réponses."""
    username: str
    content: str
    likes_count: int = 0
    is_reply: bool = False
    replies: list = field(default_factory=list)


@dataclass
class PostData:
    """Données d'un post."""
    post_url: str
    author_username: str
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    saves_count: int = 0
    caption: str = ""
