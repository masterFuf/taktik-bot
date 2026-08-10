"""AI qualification for the notifications bridge.

Qualification is not an explicit call in the per-profile pipeline: it is installed
by ``install_instagram_ai_hooks``, which patches
``InteractionEngineMixin._perform_interactions_on_profile``. Walking the pipeline
is therefore enough to trigger it, provided a service was injected.

Without an AI config the visit still extracts, persists and follows, but profiles
are not qualified — and this module says so in the logs, because a missing
qualification is indistinguishable from an empty one once stored.
"""

from __future__ import annotations

from typing import Any

from bridges.instagram.runtime.ai import create_instagram_ai_service
from bridges.instagram.runtime.ipc import _ipc, logger


def _log(level: str, message: str) -> None:
    """Log adapter for the core: stderr/loguru, never stdout.

    stdout carries the bridge's JSON contract (``notification_step`` / ``result``);
    adding narration there would corrupt it.
    """
    getattr(logger, level if level in ("info", "warning", "error", "debug") else "info")(
        f"[NOTIF-AI] {message}"
    )


def install_notifications_ai_hooks(*, ai_config: dict | None, device: Any,
                                   language: str = "en") -> bool:
    """Install the per-profile pipeline's AI qualification. True when active.

    Best-effort: an unavailable service must never fail the pass — it is announced
    and the run continues without qualification.
    """
    ai_config = ai_config or {}
    if not ai_config:
        logger.info("[NOTIF-AI] Aucune config IA fournie: les profils visites ne seront pas qualifies")
        return False
    if device is None:
        logger.warning("[NOTIF-AI] Pas de device: qualification IA desactivee")
        return False

    enabled, service = create_instagram_ai_service(ai_config=ai_config, ipc=_ipc, log=_log)
    decision_mode = (ai_config.get("decision") or {}).get("mode") == "decide"
    if not ((enabled and service) or decision_mode):
        logger.info("[NOTIF-AI] IA non activee dans la config: profils visites non qualifies")
        return False

    try:
        from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
            install_instagram_ai_hooks,
        )

        install_instagram_ai_hooks(
            ai=service,
            ai_config=ai_config,
            device=device,
            language=language,
            log=_log,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — never fatal
        logger.warning(f"[NOTIF-AI] Installation des hooks IA impossible: {exc}")
        return False


__all__ = ["install_notifications_ai_hooks"]
