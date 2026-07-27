"""Qualification IA pour le bridge Notifications.

La visite des suggestions applique le pipeline par-profil de production, et dans ce
pipeline la qualification IA n'est pas un appel explicite : elle est installee par
``install_instagram_ai_hooks``, qui patche
``InteractionEngineMixin._perform_interactions_on_profile``. Traverser le pipeline
suffit donc a la declencher — a condition qu'un service IA ait ete injecte.

Sans config IA, la visite reste utile (extraction, persistance, follow) mais les
profils ne sont pas qualifies. Ce module le DIT dans les logs : une qualification
absente ressemble sinon a une qualification vide, et c'est la meme chose vue de la
base.
"""

from __future__ import annotations

from typing import Any

from bridges.instagram.runtime.ai import create_instagram_ai_service
from bridges.instagram.runtime.ipc import _ipc, logger


def _log(level: str, message: str) -> None:
    """Adaptateur de log pour le coeur : stderr/loguru, jamais stdout.

    stdout est reserve au contrat JSON du bridge Notifications
    (``notification_step`` / ``result``) ; y ajouter la narration IA le polluerait.
    """
    getattr(logger, level if level in ("info", "warning", "error", "debug") else "info")(
        f"[NOTIF-AI] {message}"
    )


def install_notifications_ai_hooks(*, ai_config: dict | None, device: Any,
                                   language: str = "en") -> bool:
    """Installer la qualification IA du pipeline par-profil. Retourne True si active.

    Best-effort : une IA indisponible ne doit jamais faire echouer la passe — on
    l'annonce et on continue sans qualification.
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
    except Exception as exc:  # noqa: BLE001 — jamais fatal
        logger.warning(f"[NOTIF-AI] Installation des hooks IA impossible: {exc}")
        return False


__all__ = ["install_notifications_ai_hooks"]
