"""Validation helpers for the Instagram desktop automation bridge."""

from __future__ import annotations

from bridges.instagram.runtime.ipc import send_error


def format_targets_display(target: str | None) -> tuple[str, int]:
    target_list = [t.strip() for t in (target or "").split(',') if t.strip()]
    return ', '.join(target_list), len(target_list)


def validate_desktop_bridge_config(
    *,
    device_id: str | None,
    workflow_type: str | None,
    target: str | None,
) -> bool:
    if not device_id:
        send_error("Device ID is required")
        return False
    if not workflow_type:
        send_error("Workflow type is required")
        return False
    if not target:
        send_error("Target is required")
        return False
    return True
