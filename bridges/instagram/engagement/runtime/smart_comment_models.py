"""Data models for the Instagram Smart Comment bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScrapedComment:
    """A scraped comment from a post."""

    username: str
    content: str
    likes: int = 0
    is_author: bool = False
    is_reply: bool = False
    parent_username: Optional[str] = None
    position_top: int = 0
    is_qualified: bool = False
    qualification_reason: str = ""
    generated_reply: str = ""
    reply_sent: bool = False


@dataclass
class TargetProfile:
    """Scraped profile information of the target account."""

    username: str = ""
    full_name: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    posts_count: int = 0
    account_type: str = ""
    is_private: bool = False
    is_verified: bool = False


@dataclass
class PostContext:
    """Context about the target post for AI generation."""

    author_username: str = ""
    caption: str = ""
    image_description: str = ""
    likes_count: int = 0
    comments_count: int = 0
    post_date: str = ""
    target_bio: str = ""
    target_profile: Optional[dict] = None
    post_url: str = ""
