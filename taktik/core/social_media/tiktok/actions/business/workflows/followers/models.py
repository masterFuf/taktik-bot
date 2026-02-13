"""Data models for the TikTok Followers workflow."""

from typing import Dict, Any
from dataclasses import dataclass, field
import time


@dataclass
class FollowersConfig:
    """Configuration pour le workflow Followers."""
    
    # Search query (required) - username to search for
    search_query: str = ""
    
    # Nombre de followers à traiter
    max_followers: int = 50
    
    # Nombre de posts à voir par profil
    posts_per_profile: int = 2
    
    # Watch time per video (seconds)
    min_watch_time: float = 5.0
    max_watch_time: float = 15.0
    
    # Probabilités d'interaction (0.0 à 1.0)
    like_probability: float = 0.7
    comment_probability: float = 0.1
    share_probability: float = 0.05
    favorite_probability: float = 0.3
    follow_probability: float = 0.5
    story_like_probability: float = 0.5  # Probability to like stories when encountered
    
    # Limites de session
    max_likes_per_session: int = 50
    max_follows_per_session: int = 30
    max_comments_per_session: int = 10
    
    # Délai entre les actions (secondes)
    min_delay: float = 1.0
    max_delay: float = 3.0
    
    # Pauses
    pause_after_actions: int = 10
    pause_duration_min: float = 30.0
    pause_duration_max: float = 60.0
    
    # Comportement
    include_friends: bool = False  # Inclure les comptes "Friends" (déjà amis)
    skip_private_accounts: bool = False


@dataclass
class FollowersStats:
    """Statistiques du workflow Followers."""
    
    followers_seen: int = 0
    profiles_visited: int = 0
    posts_watched: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    favorites: int = 0
    follows: int = 0
    already_friends: int = 0
    skipped: int = 0
    errors: int = 0
    completion_reason: str = ''
    
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        elapsed = time.time() - self.start_time
        return {
            'followers_seen': self.followers_seen,
            'profiles_visited': self.profiles_visited,
            'posts_watched': self.posts_watched,
            'likes': self.likes,
            'comments': self.comments,
            'shares': self.shares,
            'favorites': self.favorites,
            'follows': self.follows,
            'already_friends': self.already_friends,
            'skipped': self.skipped,
            'errors': self.errors,
            'completion_reason': self.completion_reason,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
        }
