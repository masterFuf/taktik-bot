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
)
from bridges.tiktok.runtime.ipc_video_events import (
    send_action,
    send_pause,
    send_stats,
    send_video_info,
)


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
    "send_dm_conversation",
    "send_dm_progress",
    "send_dm_stats",
    "send_dm_sent",
]
