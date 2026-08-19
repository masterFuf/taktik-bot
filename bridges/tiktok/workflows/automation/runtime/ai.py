"""AI service setup for the TikTok automation bridge runtime.

Same factory as every other bridge (`taktik.core.app.ai.factory`), so TikTok classifies
against the same taxonomy as Instagram instead of quietly running free-form.
"""

from __future__ import annotations

from typing import Any, Callable

from taktik.core.app.ai.factory import create_ai_service

LogCallback = Callable[[str, str], None]


def create_tiktok_ai_service(
    *,
    ai_config: dict,
    ipc: Any = None,
    log: LogCallback = lambda level, msg: None,
) -> tuple[bool, Any | None]:
    """Create the optional OpenRouter AI service used by TikTok automation."""
    return create_ai_service(
        ai_config=ai_config,
        ipc=ipc,
        log=log,
        ready_message="TikTok AI mode enabled - Profile relevance verdict",
    )


__all__ = ["create_tiktok_ai_service"]
