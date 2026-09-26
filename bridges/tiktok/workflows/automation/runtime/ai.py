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
    report_spend: bool = True,
) -> tuple[bool, Any | None]:
    """Create the optional OpenRouter AI service used by TikTok automation.

    Without an IPC the provider reports no `ai_spend`: every TikTok qualification and comment
    was paid and never reached the cost ledger, both callers passing `ipc=None`. The bridge's
    own IPC is the default, as in the TikTok DM outreach. `report_spend=False` for a run whose
    session does not read `ai_spend` (the welcome pass)."""
    if ipc is None:
        from bridges.tiktok.runtime.ipc import _ipc as ipc
    return create_ai_service(
        ai_config=ai_config,
        ipc=ipc,
        log=log,
        ready_message="TikTok AI mode enabled - Profile relevance verdict",
        report_spend=report_spend,
    )


def install_run_ai_hooks(ai_config: dict, language: str, *, log: LogCallback = lambda level, msg: None) -> None:
    """The bridge's AI hooks for a run's `ai` block: verdicts and classifications go to stdout.

    The install is `install_profile_ai_hooks_for_run` (core), shared with the CLI; this adds the
    stdout emitters and the bridge IPC for `ai_spend`. Handed to the core launchers, which read the
    `ai` block. Does nothing when the run has no AI enabled, and never raises: a broken AI setup
    must cost the verdicts, not the run.
    """
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


def build_welcome_qualifier(ai_config: dict, language: str, *, log: LogCallback = lambda level, msg: None):
    """The new-followers welcome pass's AI verdict, verdicts and classifications on stdout.

    Handed to the core launcher, which calls it once per pass. None when no AI service can be
    built: no verdict, so no decision.

    Not `install_run_ai_hooks`: it patches `VideoInteractionMixin._interact_with_profile_posts`,
    which only the Followers and Target-profiles workflows enter; DMWorkflow does not inherit that
    mixin, so the hook would install cleanly, log "installed" and never fire once. The qualifier is
    the same function that hook runs, called directly.
    """
    from bridges.tiktok.runtime.ipc import send_profile_classification, send_relevance
    from taktik.core.social_media.tiktok.workflows.core.ai_hooks import build_tiktok_profile_qualifier

    # No `ai_spend`: the new-followers stdout reader does not store it.
    ai_enabled, ai_service = create_tiktok_ai_service(ai_config=ai_config, ipc=None, log=log,
                                                      report_spend=False)
    if not ai_enabled or ai_service is None:
        return None

    return build_tiktok_profile_qualifier(
        ai_service,
        ai_config,
        log=log,
        emit_relevance=lambda username, payload: send_relevance(
            username,
            relevant=payload.get("relevant"),
            score=payload.get("score"),
            reason=payload.get("reason"),
            follow=payload.get("follow"),
            comment=payload.get("comment"),
            like=payload.get("like"),
        ),
        emit_classification=lambda username, classification: send_profile_classification(
            username,
            classification,
            result=f"[{classification.get('niche_category', '?')}] {classification.get('niche', '?')}",
        ),
        language=language,
    )


__all__ = ["build_welcome_qualifier", "create_tiktok_ai_service", "install_run_ai_hooks"]
