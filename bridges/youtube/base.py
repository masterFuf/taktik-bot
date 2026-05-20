#!/usr/bin/env python3
"""
YouTube Bridge Base — re-exports the shared bridge infrastructure.

Kept as a thin compatibility shim so existing imports like
``from bridges.youtube.base import send_status`` continue to work.
All actual logic lives in `bridges.common.bridge_base`.
"""

from bridges.common.bridge_base import (
    _ipc,
    logger,
    send_message,
    send_status,
    send_error,
    send_log,
    send_progress,
)

__all__ = [
    "_ipc",
    "logger",
    "send_message",
    "send_status",
    "send_error",
    "send_log",
    "send_progress",
]
