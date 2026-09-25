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
    """Create the optional OpenRouter AI service used by TikTok automation.

    Without an IPC the provider reports no `ai_spend`: every TikTok qualification and comment
    was paid and never reached the cost ledger, both callers passing `ipc=None`. The bridge's
    own IPC is the default, as in the TikTok DM outreach."""
    if ipc is None:
        from bridges.tiktok.runtime.ipc import _ipc as ipc
    return create_ai_service(
        ai_config=ai_config,
        ipc=ipc,
        log=log,
        ready_message="TikTok AI mode enabled - Profile relevance verdict",
    )


def install_profile_ai_hooks(config: dict, *, log: LogCallback = lambda level, msg: None) -> None:
    """Install the profile-relevance and classification hooks for a profile-visiting run.

    The install is `install_profile_ai_hooks_for_run` (core), shared with the CLI; this wrapper
    adds the stdout emitters and the bridge IPC for `ai_spend`.

    For a runner that still reads its payload in the bridge (Post URL); Followers and Target
    Profiles hand `install_run_ai_hooks` to their core launcher, which reads the `ai` block.

    Does nothing when the run has no AI enabled, and never raises: a broken AI setup must cost
    the verdicts, not the run.
    """
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
        ai_config_from_payload,
        app_language_from_payload,
    )

    install_run_ai_hooks(ai_config_from_payload(config), app_language_from_payload(config), log=log)


def install_run_ai_hooks(ai_config: dict, language: str, *, log: LogCallback = lambda level, msg: None) -> None:
    """The bridge's AI hooks for a run's `ai` block: verdicts and classifications go to stdout."""
    if not ai_config.get("enabled"):
        return

    try:
        from bridges.tiktok.runtime.ipc import _ipc, send_profile_classification, send_relevance
        from taktik.core.social_media.tiktok.workflows.core.ai_hooks import (
            install_profile_ai_hooks_for_run,
        )

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

        install_profile_ai_hooks_for_run(ai_config, language, ai_ipc=_ipc, log=log,
                                         emit_relevance=_emit, emit_classification=_persist)
    except Exception as exc:
        log("warning", f"Could not install TikTok AI hooks: {exc}")


__all__ = ["create_tiktok_ai_service", "install_profile_ai_hooks", "install_run_ai_hooks"]
