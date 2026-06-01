"""Stdout event helpers for the TikTok Followers bridge runner."""

from __future__ import annotations

from typing import Any, Dict, List

from bridges.tiktok.runtime.ipc import send_message


def send_target_switch(current_target: str, target_idx: int, target_list: List[str]) -> None:
    """Emit the historical target-switch event."""
    send_message(
        "target_switch",
        current_target=current_target,
        target_index=target_idx,
        total_targets=len(target_list),
        next_target=target_list[target_idx + 1] if target_idx + 1 < len(target_list) else None,
    )


def send_followers_workflow_start(current_target: str, target_list: List[str], target_idx: int) -> None:
    """Emit the historical workflow-start event for a target."""
    send_message(
        "workflow_start",
        target=current_target,
        targets=target_list,
        current_target_index=target_idx,
    )


def send_final_followers_stats(total_stats: Dict[str, Any], target_count: int) -> None:
    """Emit final aggregated stats and terminal status."""
    send_message("followers_stats", stats=total_stats)
    send_message(
        "status",
        status="completed",
        message=f"Visited {total_stats['profiles_visited']} profiles across {target_count} targets",
        completion_reason=total_stats.get("completion_reason", "completed"),
    )


__all__ = [
    "send_target_switch",
    "send_followers_workflow_start",
    "send_final_followers_stats",
]
