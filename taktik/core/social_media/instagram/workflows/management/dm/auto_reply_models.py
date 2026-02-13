"""Data models for the DM Auto Reply workflow."""

from typing import List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DMAutoReplyConfig:
    """Configuration pour le workflow de réponse automatique."""
    
    # === API Configuration ===
    fal_api_key: str = ""
    llm_model: str = "meta-llama/llama-3.2-3b-instruct"  # Modèle par défaut sur fal.ai
    
    # === Persona & Contexte ===
    persona_name: str = ""
    persona_description: str = ""
    business_context: str = ""
    
    # Prompt système pour le LLM
    system_prompt: str = """Tu es un assistant qui répond aux messages Instagram de manière naturelle et engageante.
Tu dois:
- Être amical et professionnel
- Répondre de manière concise (1-3 phrases max)
- Poser des questions pour engager la conversation
- Ne jamais révéler que tu es une IA
- Adapter ton ton au contexte de la conversation"""
    
    # === Comportement ===
    # Intervalle de vérification des nouveaux messages (secondes)
    check_interval_min: int = 30
    check_interval_max: int = 120
    
    # Délai avant de répondre (pour paraître humain)
    reply_delay_min: int = 5
    reply_delay_max: int = 30
    
    # Nombre max de messages à traiter par session
    max_replies_per_session: int = 50
    
    # Durée max de la session (minutes)
    session_duration_minutes: int = 60
    
    # === Filtres ===
    # Usernames à ignorer
    ignore_usernames: List[str] = field(default_factory=list)
    
    # Mots-clés pour ignorer certains messages
    ignore_keywords: List[str] = field(default_factory=list)
    
    # Ne répondre qu'aux messages contenant ces mots-clés (vide = tous)
    respond_only_keywords: List[str] = field(default_factory=list)
    
    # === Historique ===
    # Nombre de messages précédents à inclure pour le contexte
    context_messages_count: int = 5
    
    # === Callbacks ===
    # Callback optionnel appelé avant chaque réponse
    on_before_reply: Optional[Callable] = None
    # Callback optionnel appelé après chaque réponse
    on_after_reply: Optional[Callable] = None


@dataclass
class ConversationMessage:
    """Un message dans une conversation."""
    sender: str  # 'me' ou username
    content: str
    timestamp: datetime
    is_read: bool = False


@dataclass
class Conversation:
    """Une conversation DM."""
    username: str
    messages: List[ConversationMessage] = field(default_factory=list)
    has_unread: bool = False
    last_activity: Optional[datetime] = None


@dataclass
class AutoReplyResult:
    """Résultat d'une réponse automatique."""
    username: str
    incoming_message: str
    reply_sent: str
    success: bool
    error: str = ""
    timestamp: str = ""
    llm_latency_ms: int = 0
