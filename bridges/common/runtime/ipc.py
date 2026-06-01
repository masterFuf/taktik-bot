"""
IPC (Inter-Process Communication) service for bridge scripts.
Handles structured JSON message passing between Python bridges and the Electron app.

Messages are sent via stdout (file descriptor 1) as JSON lines.
Logs go to stderr via loguru — they never interfere with IPC messages.

Usage:
    from bridges.common.runtime.ipc import IPC

    ipc = IPC()
    ipc.status("connecting", "Connecting to device...")
    ipc.error("Something went wrong")
    ipc.progress(current=5, total=100, action="scraping")
    ipc.send("custom_event", key="value")
"""

import os
import json
from typing import Any

from bridges.common.runtime.ipc_agent import AgentIpcMixin
from bridges.common.runtime.ipc_ai import AIIpcMixin
from bridges.common.runtime.ipc_dm import DMIpcMixin
from bridges.common.runtime.ipc_instagram import InstagramIpcMixin
from bridges.common.runtime.ipc_threads import ThreadsIpcMixin
from bridges.common.runtime.ipc_tiktok import TikTokIpcMixin


class IPC(InstagramIpcMixin, ThreadsIpcMixin, TikTokIpcMixin, DMIpcMixin, AIIpcMixin, AgentIpcMixin):
    """
    Structured IPC channel to the Electron desktop app.
    
    Writes JSON messages directly to the original stdout file descriptor
    to avoid interference with loguru or print() redirections.
    """

    def __init__(self):
        # Duplicate the original stdout fd BEFORE any wrapper can interfere.
        # This ensures messages always reach Electron's stdout parser.
        self._fd = None
        try:
            self._fd = os.dup(1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    def send(self, msg_type: str, **kwargs: Any) -> None:
        """Send a structured JSON message to the desktop app."""
        try:
            message = {"type": msg_type, **kwargs}
            msg_bytes = (json.dumps(message, ensure_ascii=False) + '\n').encode('utf-8')
            if self._fd is not None:
                try:
                    os.write(self._fd, msg_bytes)
                except (OSError, ValueError):
                    pass
            else:
                try:
                    os.write(1, msg_bytes)
                except (OSError, ValueError):
                    pass
        except Exception:
            pass  # Never crash on IPC failure

    # ------------------------------------------------------------------
    # Common message helpers
    # ------------------------------------------------------------------

    def status(self, status: str, message: str = "") -> None:
        """Send a status update (connecting, launching, running, etc.)."""
        self.send("status", status=status, message=message)

    def error(self, error: str, error_code: str = None) -> None:
        """Send an error message with optional error_code for i18n."""
        data = {"error": error}
        if error_code:
            data["error_code"] = error_code
        self.send("error", **data)

    def progress(self, current: int, total: int, action: str = "") -> None:
        """Send a progress update (e.g. 5/100 profiles scraped)."""
        self.send("progress", current=current, total=total, action=action)

    def log(self, level: str, message: str) -> None:
        """Send a log message to the desktop debug console."""
        self.send("log", level=level, message=message)

    def stats(self, **stats: Any) -> None:
        """Send stats update (platform-agnostic)."""
        self.send("stats", stats=stats)

    def session_start(self, session_id: int, **kwargs) -> None:
        """Send session start event with session ID."""
        self.send("session_start", session_id=session_id, **kwargs)
