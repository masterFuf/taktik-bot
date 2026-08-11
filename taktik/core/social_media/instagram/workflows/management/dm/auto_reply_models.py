"""Data models for the DM Auto Reply workflow."""

from typing import List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from taktik.core.app.ai.providers.openrouter import MODEL_GENERATION


@dataclass
class DMAutoReplyConfig:
    """Configuration for the auto-reply workflow."""

    # === API Configuration ===
    openrouter_api_key: str = ""
    # DM reply is generation: single model read from the central constant, never hardcoded.
    llm_model: str = MODEL_GENERATION
    
    # === Persona & Contexte ===
    persona_name: str = ""
    persona_description: str = ""
    business_context: str = ""
    
    # System prompt for the LLM
    system_prompt: str = """Tu es un assistant qui répond aux messages Instagram de manière naturelle et engageante.
Tu dois:
- Être amical et professionnel
- Répondre de manière concise (1-3 phrases max)
- Poser des questions pour engager la conversation
- Ne jamais révéler que tu es une IA
- Adapter ton ton au contexte de la conversation"""
    
    # === Comportement ===
    # New-message polling interval (seconds)
    check_interval_min: int = 30
    check_interval_max: int = 120
    
    # Delay before replying (to read as human)
    reply_delay_min: int = 5
    reply_delay_max: int = 30
    
    # Max messages handled per session
    max_replies_per_session: int = 50
    
    # Max session duration (minutes)
    session_duration_minutes: int = 60
    
    # === Filtres ===
    # Usernames à ignorer
    ignore_usernames: List[str] = field(default_factory=list)
    
    # Keywords marking a message as ignored
    ignore_keywords: List[str] = field(default_factory=list)
    
    # Only reply to messages carrying these keywords (empty = all)
    respond_only_keywords: List[str] = field(default_factory=list)
    
    # === History ===
    # Number of previous messages included as context
    context_messages_count: int = 5
    
    # === Callbacks ===
    # Optional callback, before each reply
    on_before_reply: Optional[Callable] = None
    # Optional callback, after each reply
    on_after_reply: Optional[Callable] = None


@dataclass
class ConversationMessage:
    """One message in a conversation."""
    sender: str  # 'me' ou username
    content: str
    timestamp: datetime
    is_read: bool = False


@dataclass
class Conversation:
    """One DM conversation."""
    username: str
    messages: List[ConversationMessage] = field(default_factory=list)
    has_unread: bool = False
    last_activity: Optional[datetime] = None


@dataclass
class AutoReplyResult:
    """Result of one automatic reply."""
    username: str
    incoming_message: str
    reply_sent: str
    success: bool
    error: str = ""
    timestamp: str = ""
    llm_latency_ms: int = 0
