"""Application AI integrations for TAKTIK."""

from taktik.core.app.ai.comments.comment_ai import UserProfile
from taktik.core.app.ai.providers.openrouter import (
    AIService, MODEL_ANALYSIS, MODEL_GENERATION, DEFAULT_TEXT_MODEL, DEFAULT_VISION_MODEL,
)

__all__ = [
    "AIService", "MODEL_ANALYSIS", "MODEL_GENERATION",
    "DEFAULT_TEXT_MODEL", "DEFAULT_VISION_MODEL", "UserProfile",
]
