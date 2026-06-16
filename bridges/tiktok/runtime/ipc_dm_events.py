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


def send_new_follower(follower: Dict[str, Any]) -> None:
    """Send a scraped new-follower item to desktop app (inbox v2)."""
    _ipc.new_follower(follower)


def send_follow_back_result(result: Dict[str, Any]) -> None:
    """Send a follow-back execution result to desktop app (inbox v2)."""
    _ipc.follow_back_result(result)


def send_unreplied_conversation(conversation: Dict[str, Any]) -> None:
    """Send a scraped conversation + unreplied flag to desktop app (inbox v2 phase 2)."""
    _ipc.unreplied_conversation(conversation)


def send_message_request(request: Dict[str, Any]) -> None:
    """Send a scraped message request to desktop app (inbox v2 phase 3)."""
    _ipc.message_request(request)


def send_request_result(result: Dict[str, Any]) -> None:
    """Send a message-request decision result to desktop app (inbox v2 phase 3)."""
    _ipc.request_result(result)


__all__ = [
    "send_dm_conversation",
    "send_dm_progress",
    "send_dm_stats",
    "send_dm_sent",
    "send_new_follower",
    "send_follow_back_result",
    "send_unreplied_conversation",
    "send_message_request",
    "send_request_result",
]
