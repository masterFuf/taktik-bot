"""TikTok-specific stdout IPC facade for bridge runtime code."""

from bridges.common.runtime.bridge_base import (
    _ipc,
    get_workflow,
    logger,
    send_error,
    send_log,
    send_message,
    send_progress,
    send_status,
    set_workflow,
    signal_handler,
)
from bridges.tiktok.runtime.ipc_dm_events import (
    send_dm_conversation,
    send_dm_progress,
    send_dm_sent,
    send_dm_stats,
    send_activity_notification,
    send_follow_back_result,
    send_message_request,
    send_new_follower,
    send_request_result,
    send_unreplied_conversation,
)
from bridges.tiktok.runtime.ipc_video_events import (
    send_action,
    send_pause,
    send_relevance,
    send_stats,
    send_video_info,
)


def _register_telemetry_sink() -> None:
    """Forward fine-grained step telemetry (keystrokes/taps/scrolls emitted by the shared
    humanization primitives, which TikTok reuses) to stdout as `step_metric` JSON lines —
    same contract as the Instagram bridge, so the Lab metrics work for TikTok too."""
    try:
        from taktik.core.shared.telemetry import configure_telemetry_sink

        def _sink(metric) -> None:
            _ipc.send(
                "step_metric",
                category=metric.category,
                action=metric.action,
                target=metric.target,
                detail=metric.detail,
                ts=metric.ts,
            )

        configure_telemetry_sink(_sink)
    except Exception as exc:
        logger.debug(f"Could not register telemetry sink: {exc}")


_register_telemetry_sink()


__all__ = [
    "_ipc",
    "logger",
    "send_message",
    "send_status",
    "send_error",
    "send_log",
    "send_progress",
    "get_workflow",
    "set_workflow",
    "signal_handler",
    "send_stats",
    "send_video_info",
    "send_action",
    "send_pause",
    "send_relevance",
    "send_dm_conversation",
    "send_dm_progress",
    "send_dm_stats",
    "send_dm_sent",
    "send_new_follower",
    "send_follow_back_result",
    "send_unreplied_conversation",
    "send_message_request",
    "send_request_result",
    "send_activity_notification",
]
