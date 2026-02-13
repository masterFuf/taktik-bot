"""Data models for the TikTok DM workflow.

Contains configuration, statistics, and conversation data structures.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import time


@dataclass
class DMConfig:
    """Configuration pour le workflow DM."""
    
    # Nombre de conversations à lire
    max_conversations: int = 20
    
    # Filtres
    skip_notifications: bool = True  # Ignorer New followers, Activity, System
    skip_groups: bool = False  # Ignorer les conversations de groupe
    only_unread: bool = False  # Seulement les conversations non lues
    
    # Délais
    delay_between_conversations: float = 1.0
    delay_after_send: float = 0.5
    
    # Comportement
    mark_as_read: bool = True  # Marquer comme lu après lecture
    close_sticker_suggestions: bool = True  # Fermer les suggestions de stickers


@dataclass
class DMStats:
    """Statistiques du workflow DM."""
    
    conversations_read: int = 0
    messages_read: int = 0
    messages_sent: int = 0
    groups_skipped: int = 0
    notifications_skipped: int = 0
    errors: int = 0
    
    start_time: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary."""
        elapsed = time.time() - self.start_time
        return {
            'conversations_read': self.conversations_read,
            'messages_read': self.messages_read,
            'messages_sent': self.messages_sent,
            'groups_skipped': self.groups_skipped,
            'notifications_skipped': self.notifications_skipped,
            'errors': self.errors,
            'elapsed_seconds': elapsed,
            'elapsed_formatted': f"{int(elapsed // 60)}m {int(elapsed % 60)}s",
        }


@dataclass
class ConversationData:
    """Data for a single conversation."""
    
    name: str
    is_group: bool = False
    member_count: Optional[int] = None
    messages: List[Dict[str, Any]] = field(default_factory=list)
    last_message: Optional[str] = None
    timestamp: Optional[str] = None
    unread_count: int = 0
    can_reply: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'is_group': self.is_group,
            'member_count': self.member_count,
            'messages': self.messages,
            'last_message': self.last_message,
            'timestamp': self.timestamp,
            'unread_count': self.unread_count,
            'can_reply': self.can_reply,
        }
