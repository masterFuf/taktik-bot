"""Data models for the TikTok For You workflow."""

from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class ForYouConfig:
    """Configuration pour le workflow For You."""
    
    # Nombre de vidéos à traiter
    max_videos: int = 50
    
    # Temps de visionnage (secondes)
    min_watch_time: float = 2.0
    max_watch_time: float = 8.0
    
    # Probabilités d'action (0.0 à 1.0)
    like_probability: float = 0.3
    follow_probability: float = 0.1
    favorite_probability: float = 0.05
    
    # Filtres
    min_likes: Optional[int] = None  # Minimum de likes pour interagir
    max_likes: Optional[int] = None  # Maximum de likes pour interagir
    required_hashtags: List[str] = field(default_factory=list)  # Hashtags requis
    excluded_hashtags: List[str] = field(default_factory=list)  # Hashtags exclus
    
    # Limites de session
    max_likes_per_session: int = 50
    max_follows_per_session: int = 20
    
    # Pauses
    pause_after_actions: int = 10  # Pause après N actions
    pause_duration_min: float = 30.0
    pause_duration_max: float = 60.0
    
    # Comportement
    skip_already_liked: bool = True
    skip_already_followed: bool = True
    skip_ads: bool = True  # Skip les publicités automatiquement
    follow_back_suggestions: bool = False  # Si True, follow back les suggestions. Si False, click "Not interested"
