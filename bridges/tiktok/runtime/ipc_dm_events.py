"""TikTok DM IPC event helpers."""

from __future__ import annotations

from typing import Any, Dict

from bridges.common.runtime.bridge_base import _ipc


def send_dm_conversation(conversation: Dict[str, Any]) -> None:
    """Send a conversation data to desktop app."""
    _ipc.dm_conversation(conversation)


def send_dm_progress(current: int, total: int, name: str) -> None:
    """Send DM reading progress to desktop app."""
    _ipc.dm_progress(current, total, name)


def send_dm_stats(stats: Dict[str, Any]) -> None:
    """Send DM workflow stats to desktop app."""
    _ipc.dm_stats(stats)


def send_dm_sent(conversation: str, success: bool, error: str = None) -> None:
    """Send DM sent result to desktop app."""
    _ipc.dm_sent(conversation, success, error)


__all__ = ["send_dm_conversation", "send_dm_progress", "send_dm_stats", "send_dm_sent"]
