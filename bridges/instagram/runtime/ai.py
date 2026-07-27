"""Service IA partage par les flows Instagram du bridge.

Owner runtime plateforme (AGENTS) : plusieurs flows en ont besoin — l'automation
(target / hashtag / feed) et l'engagement Notifications, dont la visite des
suggestions applique le meme pipeline par-profil, qualification IA comprise. La
fabrique vit donc ici et non chez l'un des deux appelants.
"""

from __future__ import annotations

from typing import Any, Callable


LogCallback = Callable[[str, str], None]


def create_instagram_ai_service(
    *,
    ai_config: dict,
    ipc: Any,
    log: LogCallback,
) -> tuple[bool, Any | None]:
    """Create the optional OpenRouter AI service used by Instagram flows."""
    if not ai_config.get("enabled", False):
        return False, None

    api_key = ai_config.get("openrouterApiKey", "")
    if not (api_key and len(api_key) > 5):
        log("warning", "AI mode requested but no OpenRouter API key provided")
        return False, None

    from taktik.core.app.ai.providers.openrouter import AIService

    vision_model = ai_config.get("visionModel") or None
    service = AIService(api_key=api_key, ipc=ipc, vision_model=vision_model)
    log("info", "AI mode enabled - Smart Comments / Profile Analysis / Post Analysis")
    return True, service


__all__ = ["create_instagram_ai_service"]
