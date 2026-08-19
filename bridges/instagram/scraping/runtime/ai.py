"""AI provider factory for the Instagram scraping bridge."""

from __future__ import annotations

from taktik.core.app.ai.factory import build_ai_service


def build_scraping_ai_service(*, api_key: str, ipc=None, vision_model: str = None, text_model: str = None,
                              niche_taxonomy: dict = None):
    """Build the bridge-owned AI provider injected into scraping workflows."""
    return build_ai_service(api_key=api_key, ipc=ipc, vision_model=vision_model,
                            text_model=text_model, niche_taxonomy=niche_taxonomy)


__all__ = ["build_scraping_ai_service"]
