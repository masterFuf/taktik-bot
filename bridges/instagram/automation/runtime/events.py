"""Bridge event emitters for Instagram desktop automation runtime."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error, send_message, send_stats


def send_instagram_session_config(config: dict, *, ai_enabled: bool) -> None:
    from taktik.core.social_media.instagram.workflows.core.config_builder import (
        build_instagram_session_config_event,
    )

    send_message(
        "session_config",
        config=build_instagram_session_config_event(
            config,
            ai_enabled=ai_enabled,
        ),
    )


def send_instagram_workflow_final_stats(stats: dict) -> None:
    send_stats(
        likes=stats.get("likes", 0),
        follows=stats.get("follows", 0),
        comments=stats.get("comments", 0),
        profiles=stats.get("interactions", 0),
        unfollows=stats.get("unfollows", 0),
    )


def send_instagram_workflow_error(error: Exception) -> None:
    error_msg = str(error)
    if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
        send_error(
            f"UIAutomator2 crashed during workflow: {error_msg}",
            error_code="ATX_AGENT_CRASHED",
        )
    elif "timeout" in error_msg.lower():
        send_error(f"Workflow timed out: {error_msg}", error_code="WORKFLOW_TIMEOUT")
    else:
        send_error(f"Workflow error: {error_msg}", error_code="WORKFLOW_ERROR")
