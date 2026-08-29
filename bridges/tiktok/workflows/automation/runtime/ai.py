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


def install_profile_ai_hooks(config: dict, *, log: LogCallback = lambda level, msg: None) -> None:
    """Install the profile-relevance and classification hooks for a profile-visiting run.

    Lives here rather than beside one runner because two workflows visit profiles the same way —
    followers and target-profiles — and a second copy is how one of them ends up without the AI
    verdict, or persisting under the wrong platform.

    Does nothing when the run has no AI enabled, and never raises: a broken AI setup must cost
    the verdicts, not the run.
    """
    ai_config = config.get("ai") or {}
    if not ai_config.get("enabled"):
        return

    try:
        from bridges.tiktok.runtime.ipc import send_profile_classification, send_relevance
        from taktik.core.social_media.tiktok.workflows.core.ai_hooks import install_tiktok_ai_hooks

        ai_enabled, ai_service = create_tiktok_ai_service(ai_config=ai_config, ipc=None, log=log)
        if not ai_enabled:
            return

        def _emit(username: str, payload: dict) -> None:
            send_relevance(
                username,
                relevant=payload.get("relevant"),
                score=payload.get("score"),
                reason=payload.get("reason"),
                follow=payload.get("follow"),
                comment=payload.get("comment"),
                like=payload.get("like"),
            )

        def _persist(username: str, classification: dict) -> None:
            send_profile_classification(
                username,
                classification,
                result=f"[{classification.get('niche_category', '?')}] {classification.get('niche', '?')}",
            )

        app_language = config.get("language") or config.get("appLanguage") or "en"
        install_tiktok_ai_hooks(ai_service, ai_config, log=log, emit_relevance=_emit,
                                emit_classification=_persist, language=app_language)
    except Exception as exc:
        log("warning", f"Could not install TikTok AI hooks: {exc}")


__all__ = ["create_tiktok_ai_service", "install_profile_ai_hooks"]
