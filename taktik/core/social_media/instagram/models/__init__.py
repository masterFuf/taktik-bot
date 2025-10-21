"""
Modèles de données pour Instagram.

Ce package contient les modèles de données utilisés dans le module Instagram :
- Post: Représente un post Instagram
- User: Représente un utilisateur Instagram
- Story: Représente une story Instagram
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

__all__ = ['Post', 'User', 'Story']

@dataclass
class Post:
    """Modèle représentant un post Instagram."""
    id: str
    username: str
    caption: Optional[str] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    timestamp: Optional[datetime] = None
    is_video: bool = False
    is_carousel: bool = False
    media_urls: List[str] = field(default_factory=list)
    location: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit le post en dictionnaire."""
        return {
            'id': self.id,
            'username': self.username,
            'caption': self.caption,
            'like_count': self.like_count,
            'comment_count': self.comment_count,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_video': self.is_video,
            'is_carousel': self.is_carousel,
            'media_urls': self.media_urls,
            'location': self.location
        }

@dataclass
class User:
    """Modèle représentant un utilisateur Instagram."""
    username: str
    full_name: Optional[str] = None
    biography: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None
    is_private: bool = False
    is_verified: bool = False
    profile_pic_url: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'utilisateur en dictionnaire."""
        return {
            'username': self.username,
            'full_name': self.full_name,
            'biography': self.biography,
            'followers_count': self.followers_count,
            'following_count': self.following_count,
            'posts_count': self.posts_count,
            'is_private': self.is_private,
            'is_verified': self.is_verified,
            'profile_pic_url': self.profile_pic_url
        }

@dataclass
class Story:
    """Modèle représentant une story Instagram."""
    id: str
    username: str
    timestamp: datetime
    media_url: str
    media_type: str  # 'image' ou 'video'
    duration: Optional[float] = None  # Pour les vidéos
    mentions: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit la story en dictionnaire."""
        return {
            'id': self.id,
            'username': self.username,
            'timestamp': self.timestamp.isoformat(),
            'media_url': self.media_url,
            'media_type': self.media_type,
            'duration': self.duration,
            'mentions': self.mentions,
            'hashtags': self.hashtags
        }
