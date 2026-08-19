"""AI service shared by the bridge Instagram flows.

Owner runtime plateforme (AGENTS) : plusieurs flows en ont besoin — l'automation
and the notifications engagement, whose suggestions visit walks the same
per-profile pipeline, qualification included. The factory therefore lives here
rather than in either caller.

It is a thin alias over `taktik.core.app.ai.factory.create_ai_service`: this module used to
build the AIService itself and forgot the premium taxonomy, so automation runs classified
against a free-form taxonomy while scraping runs classified against the real one. Building
the service is now one function for the whole product.
"""

from __future__ import annotations

from typing import Any, Callable

from taktik.core.app.ai.factory import create_ai_service

LogCallback = Callable[[str, str], None]


def create_instagram_ai_service(
    *,
    ai_config: dict,
    ipc: Any,
    log: LogCallback,
) -> tuple[bool, Any | None]:
    """Create the optional OpenRouter AI service used by Instagram flows."""
    return create_ai_service(
        ai_config=ai_config,
        ipc=ipc,
        log=log,
        ready_message="AI mode enabled - Smart Comments / Profile Analysis / Post Analysis",
    )


__all__ = ["create_instagram_ai_service"]
