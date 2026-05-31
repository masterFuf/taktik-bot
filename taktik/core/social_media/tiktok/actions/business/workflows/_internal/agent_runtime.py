"""Shared Agent-runtime adapter primitives for TikTok business workflows."""

from __future__ import annotations

from typing import Any, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation


def merge_invocation_payload(invocation: WorkflowInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Merge executor variables and step params, keeping step params authoritative."""
    merged = dict(payload)
    merged.update(invocation.params)
    return merged


def attach_video_callbacks(workflow: Any, notifier: Any) -> None:
    """Forward standard video workflow callbacks to an injected notifier."""
    if notifier is None:
        return

    if hasattr(workflow, "set_on_video_callback"):
        workflow.set_on_video_callback(lambda video: notify(notifier, "video_info", video=video))
    if hasattr(workflow, "set_on_like_callback"):
        workflow.set_on_like_callback(
            lambda video: notify(notifier, "action", action="like", target=video.get("author", ""))
        )
    if hasattr(workflow, "set_on_follow_callback"):
        workflow.set_on_follow_callback(
            lambda video: notify(notifier, "action", action="follow", target=video.get("author", ""))
        )
    if hasattr(workflow, "set_on_stats_callback"):
        workflow.set_on_stats_callback(lambda stats: notify(notifier, "tiktok_stats", stats=stats))
    if hasattr(workflow, "set_on_pause_callback"):
        workflow.set_on_pause_callback(lambda duration: notify(notifier, "pause", duration=duration))


def notify(notifier: Any, event_type: str, **payload: Any) -> None:
    """Send a notifier event through a generic send method or named callback."""
    sender = getattr(notifier, "send", None)
    if callable(sender):
        sender(event_type, **payload)
        return
    method = getattr(notifier, event_type, None)
    if callable(method):
        method(**payload)


def int_param(payload: Mapping[str, Any], *names: str, default: int) -> int:
    return int(value_param(payload, *names, default=default))


def optional_int_param(payload: Mapping[str, Any], *names: str) -> int | None:
    value = value_param(payload, *names, default=None)
    return int(value) if value is not None else None


def float_param(payload: Mapping[str, Any], *names: str, default: float) -> float:
    return float(value_param(payload, *names, default=default))


def probability_param(payload: Mapping[str, Any], *names: str, default: float) -> float:
    value = float(value_param(payload, *names, default=default))
    return value / 100.0 if value > 1 else value


def bool_param(payload: Mapping[str, Any], *names: str, default: bool) -> bool:
    value = value_param(payload, *names, default=default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def list_param(payload: Mapping[str, Any], *names: str) -> list[str]:
    value = value_param(payload, *names, default=[])
    if isinstance(value, str):
        return [item.strip().lstrip("#") for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip().lstrip("#") for item in value if str(item).strip()]
    return []


def value_param(payload: Mapping[str, Any], *names: str, default: Any) -> Any:
    for name in names:
        value = payload.get(name)
        if value is not None:
            return value
    return default
