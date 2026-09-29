"""The AI service the desktop's notifications pass qualifies its visited profiles with.

The qualification itself (hooks, decision mode, fallbacks) is the core's
(`workflows/notifications/ai.py`); the bridge only builds the service, without spend
reporting: nothing on the desktop side reads it for this pass.
"""

from __future__ import annotations

from typing import Any, Mapping

from bridges.instagram.common.ai import create_instagram_ai_service
from bridges.instagram.common.ipc import _ipc, logger


def _log(level: str, message: str) -> None:
    """Log adapter: stderr/loguru, never stdout (the bridge's JSON contract)."""
    getattr(logger, level if level in ("info", "warning", "error", "debug") else "info")(
        f"[NOTIF-AI] {message}"
    )


def notifications_ai_service(ai_config: Mapping[str, Any]):
    """The service the pass asks for, or None when AI is off or unavailable."""
    enabled, service = create_instagram_ai_service(ai_config=dict(ai_config), ipc=_ipc, log=_log,
                                                   report_spend=False)
    return service if enabled else None


__all__ = ["notifications_ai_service"]
