"""
User profile model for TAKTIK AI features.

`UserProfile` is the operator's identity/goals block, configured once and reused across AI
features (comments, DMs, persona). It is the only surviving export of this module: the former
fal.ai comment/vision stack (`analyze_post_image`, `qualify_comments`, `generate_replies`, the
`_fal_request`/`_call_llm` helpers and the `FAL_*`/`claude-3-5-sonnet` model literals) was dead
code — never wired anywhere — and has been removed. Every LLM call now goes through the central
`AIService` (`taktik/core/app/ai/providers/openrouter.py`) on the two fixed models.
"""

from typing import Dict, Any
from dataclasses import dataclass


# =============================================================================
# USER PROFILE — The core identity that drives all AI decisions
# =============================================================================

@dataclass
class UserProfile:
    """
    Represents the bot operator's identity and goals.
    This is configured ONCE and used across ALL AI features (comments, DMs, etc).
    Stored persistently in Electron config.
    """
    # Identity
    username: str = ""
    bio: str = ""
    niche: str = ""
    platform: str = "instagram"

    # Goals & context
    objective: str = ""          # What the user wants to achieve (e.g. "gain clients for my social media agency")
    services: str = ""           # What the user offers (e.g. "organic growth strategies, content creation")
    target_audience: str = ""    # Who the user targets (e.g. "small businesses wanting social media visibility")

    # Personality & tone (free text, LLM interprets it)
    personality: str = ""        # e.g. "friendly expert who gives genuine advice"

    # Extra context the user wants the AI to know
    custom_context: str = ""     # Free-form additional info

    def to_prompt_block(self) -> str:
        """Convert profile to a prompt block for the LLM."""
        parts = []
        if self.username:
            parts.append(f"Username: @{self.username}")
        if self.bio:
            parts.append(f"Bio: {self.bio}")
        if self.niche:
            parts.append(f"Niche: {self.niche}")
        if self.platform:
            parts.append(f"Platform: {self.platform}")
        if self.objective:
            parts.append(f"Objective: {self.objective}")
        if self.services:
            parts.append(f"Services/Products: {self.services}")
        if self.target_audience:
            parts.append(f"Target audience: {self.target_audience}")
        if self.personality:
            parts.append(f"Personality/Tone: {self.personality}")
        if self.custom_context:
            parts.append(f"Additional context: {self.custom_context}")
        return "\n".join(parts) if parts else "No profile configured."

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Create from dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})
