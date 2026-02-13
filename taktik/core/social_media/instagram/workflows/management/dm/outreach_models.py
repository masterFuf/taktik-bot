"""Data models for the DM Outreach workflow."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class DMOutreachConfig:
    """Configuration pour le workflow d'outreach DM."""
    
    # Liste des destinataires (usernames)
    recipients: List[str] = field(default_factory=list)
    
    # Message à envoyer (peut contenir des variables: {username}, {name})
    message_template: str = ""
    
    # Messages alternatifs pour A/B testing
    message_variants: List[str] = field(default_factory=list)
    
    # Délais entre les messages (en secondes)
    delay_min: int = 30
    delay_max: int = 120
    
    # Limite de messages par session
    max_messages_per_session: int = 20
    
    # Pause longue après X messages
    pause_after_messages: int = 10
    pause_duration_min: int = 300  # 5 minutes
    pause_duration_max: int = 600  # 10 minutes
    
    # Vérifier si déjà en conversation avant d'envoyer
    skip_existing_conversations: bool = True
    
    # Suivre avant d'envoyer le message (optionnel)
    follow_before_dm: bool = False


@dataclass
class DMOutreachResult:
    """Résultat d'un envoi de DM."""
    username: str
    success: bool
    message_sent: str = ""
    error: str = ""
    timestamp: str = ""
