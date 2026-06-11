"""AI service setup for the TikTok automation bridge runtime.

Mirror of `bridges/instagram/automation/runtime/ai.py` — creates the optional OpenRouter
AI service from the run's `ai` config (injected main-side with the OpenRouter key).
"""

from __future__ import annotations

from typing import Any, Callable

LogCallback = Callable[[str, str], None]


def create_tiktok_ai_service(
    *,
    ai_config: dict,
    ipc: Any = None,
    log: LogCallback = lambda level, msg: None,
) -> tuple[bool, Any | None]:
    """Create the optional OpenRouter AI service used by TikTok automation."""
    if not ai_config.get("enabled", False):
        return False, None

    api_key = ai_config.get("openrouterApiKey", "")
    if not (api_key and len(api_key) > 5):
        log("warning", "AI mode requested but no OpenRouter API key provided")
        return False, None

    from taktik.core.app.ai.providers.openrouter import AIService

    vision_model = ai_config.get("visionModel") or None
    service = AIService(api_key=api_key, ipc=ipc, vision_model=vision_model)
    log("info", "TikTok AI mode enabled - Profile relevance verdict")
    return True, service
