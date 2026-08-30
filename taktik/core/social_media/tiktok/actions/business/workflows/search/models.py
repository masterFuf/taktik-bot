"""Data models for the TikTok Search workflow."""

from typing import Optional, List
from dataclasses import dataclass, field


@dataclass
class SearchConfig:
    """Configuration of the search workflow."""
    
    # Search query (required)
    search_query: str = ""
    
    # Nombre de vidéos à traiter
    max_videos: int = 50
    
    # Temps de visionnage (secondes)
    min_watch_time: float = 2.0
    max_watch_time: float = 8.0
    
    # Probabilités d'action (0.0 à 1.0)
    like_probability: float = 0.3
    follow_probability: float = 0.1
    favorite_probability: float = 0.05
    #: Commenting reached this road on 2026-08-30, through the shared `VideoCommentMixin`. Zero
    #: by default: a feed run that never asked to comment must behave exactly as it did before.
    comment_probability: float = 0.0
    max_comments_per_session: int = 10
    #: The run's own comment texts. Empty and never defaulted to a built-in list — a generic
    #: "Nice!" under a stranger's video is the most recognisable bot signature there is.
    comment_texts: List[str] = field(default_factory=list)
    
    # Filtres
    min_likes: Optional[int] = None
    max_likes: Optional[int] = None
    
    # Limites de session
    max_likes_per_session: int = 50
    max_follows_per_session: int = 20
    
    # Pauses
    pause_after_actions: int = 10
    pause_duration_min: float = 30.0
    pause_duration_max: float = 60.0
    
    # Comportement
    skip_already_liked: bool = True
    skip_already_followed: bool = True
    skip_ads: bool = True
