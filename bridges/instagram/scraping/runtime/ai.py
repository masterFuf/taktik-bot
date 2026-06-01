"""AI provider factory for the Instagram scraping bridge."""

from __future__ import annotations

from taktik.core.app.ai.providers.openrouter import AIService


def build_scraping_ai_service(*, api_key: str, ipc=None, vision_model: str = None, text_model: str = None):
    """Build the bridge-owned AI provider injected into scraping workflows."""
    return AIService(api_key=api_key, ipc=ipc, vision_model=vision_model, text_model=text_model)
