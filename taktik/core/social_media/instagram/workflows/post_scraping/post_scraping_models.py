"""Data models for the Post Scraping workflow."""

from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PostStats:
    """Statistics for a post."""
    post_url: str
    author_username: str
    likes_count: int = 0
    comments_count: int = 0
    shares_count: int = 0
    saves_count: int = 0
    caption: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CommentData:
    """Represents a comment with its replies."""
    username: str
    content: str
    likes_count: int = 0
    is_author_reply: bool = False
    parent_comment_id: Optional[int] = None
    replies: List['CommentData'] = field(default_factory=list)
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class ScrapedProfile:
    """Profile data scraped from a liker or commenter."""
    username: str
    source_type: str  # 'liker' or 'commenter'
    source_post_url: str
    
    # Profile data
    bio: Optional[str] = None
    website: Optional[str] = None
    threads_username: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    is_private: bool = False
    is_verified: bool = False
    is_business: bool = False
    category: Optional[str] = None
    
    # Engagement context
    comment_content: Optional[str] = None
    comment_likes: int = 0
    
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
