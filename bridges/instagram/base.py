#!/usr/bin/env python3
"""
Instagram Bridge Base facade.

Common scaffolding lives in `bridges.common.runtime.bridge_base`.
Instagram-specific runtime capabilities live under `bridges.instagram.runtime`.
"""

import sys

from bridges.instagram.runtime.bridge import InstagramBridgeBase, _CloneAwareDeviceProxy
from bridges.instagram.runtime.ipc import (
    _ipc,
    get_workflow,
    logger,
    send_current_post,
    send_error,
    send_feed_decision,
    send_follow_event,
    send_instagram_action,
    send_instagram_profile_visit,
    send_instagram_stats,
    send_like_event,
    send_log,
    send_message,
    send_post_skipped,
    send_story_event,
    send_profile_captured,
    send_profile_skipped,
    send_progress,
    send_scraping_dq_progress,
    send_scraping_profile_visit,
    send_stats,
    send_status,
    send_unfollow_event,
    set_workflow,
    setup_stats_callback,
    signal_handler,
)


def _register_core_ipc_emitter() -> None:
    """Expose bridge IPC helpers to core workflows without core importing bridges."""
    try:
        from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter

        IPCEmitter.configure_bridge_adapter(sys.modules[__name__])
    except Exception as exc:
        logger.debug(f"Could not register core IPC emitter adapter: {exc}")


_register_core_ipc_emitter()


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
    "send_post_skipped",
    "send_current_post",
    "setup_stats_callback",
    "InstagramBridgeBase",
    "_CloneAwareDeviceProxy",
]
