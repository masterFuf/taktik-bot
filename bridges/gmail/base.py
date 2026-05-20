#!/usr/bin/env python3
"""
Gmail Bridge Base — re-exports the shared bridge infrastructure.

Kept as a thin compatibility shim so existing imports like
``from bridges.gmail.base import send_status`` continue to work.
All actual logic lives in `bridges.common.bridge_base`.
"""

# Bootstrap (sys.path + UTF-8 + loguru) is performed transitively
# by importing from bridges.common.bridge_base.
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
