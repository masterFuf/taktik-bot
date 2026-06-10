"""Instagram-specific stdout IPC helpers for bridge runtime code."""

import sys

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
from bridges.instagram.runtime.ipc_interaction_events import (
    send_feed_decision,
    send_follow_event,
    send_instagram_action,
    send_instagram_profile_visit,
    send_like_event,
    send_story_event,
    send_unfollow_event,
)
from bridges.instagram.runtime.ipc_scraping_events import (
    send_current_post,
    send_post_skipped,
    send_profile_captured,
    send_profile_skipped,
    send_scraping_dq_progress,
    send_scraping_profile_visit,
)
from bridges.instagram.runtime.ipc_stats import (
    send_instagram_stats,
    send_stats,
    setup_stats_callback,
)


def _register_core_ipc_emitter() -> None:
    """Expose Instagram IPC helpers to core workflows without core importing bridges."""
    try:
        from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter

        IPCEmitter.configure_bridge_adapter(sys.modules[__name__])
    except Exception as exc:
        logger.debug(f"Could not register core IPC emitter adapter: {exc}")


def _register_telemetry_sink() -> None:
    """Forward fine-grained step telemetry (keystrokes/taps/scrolls/follower decisions)
    emitted by the shared primitives to stdout as `step_metric` JSON lines."""
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


_register_core_ipc_emitter()
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
    "send_instagram_stats",
    "send_instagram_action",
    "send_instagram_profile_visit",
    "send_unfollow_event",
    "send_follow_event",
    "send_like_event",
    "send_story_event",
    "send_feed_decision",
    "send_profile_captured",
    "send_profile_skipped",
    "send_scraping_profile_visit",
    "send_scraping_dq_progress",
    "send_post_skipped",
    "send_current_post",
    "setup_stats_callback",
]
