#!/usr/bin/env python3
"""
TikTok Bridge Base facade.

Common scaffolding lives in `bridges.common.runtime.bridge_base`.
TikTok-specific runtime capabilities live under `bridges.tiktok.runtime`.
"""

from bridges.tiktok.runtime.ipc import (
    _ipc,
    get_workflow,
    logger,
    send_action,
    send_dm_conversation,
    send_dm_progress,
    send_dm_sent,
    send_dm_stats,
    send_error,
    send_log,
    send_message,
    send_pause,
    send_progress,
    send_stats,
    send_status,
    send_video_info,
    set_workflow,
    signal_handler,
)
from bridges.tiktok.runtime.startup import tiktok_startup
from bridges.tiktok.runtime.video_callbacks import setup_video_workflow_callbacks, send_final_video_stats

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
    "tiktok_startup",
    "setup_video_workflow_callbacks",
    "send_final_video_stats",
]
