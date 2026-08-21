"""Agent runtime handlers for Instagram tasks.

A task is a one-shot: it runs against no target list, produces no live panel and holds the
device for a few seconds. `account` and `publish` have behaved this way from the start —
they were filed under other families because there was no shelf for one-shots, which is why
`SESSION_WORKFLOW_TYPES` had to grow them as retrofitted "dedicated families".

Registering them here rather than inventing a parallel mechanism is the point: the Agent
registry is already an `id -> handler` map that the CLI, the scheduler and the desktop all
resolve through. A task needed the shelf, not a new engine.
"""

from __future__ import annotations

from typing import Any, Mapping

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.tasks.story_relay import (
    DEFAULT_MAX_STORIES,
    relay_source_stories,
)

INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID = "instagram.task.story_relay"
INSTAGRAM_TASK_WORKFLOW_IDS = (INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID,)


def build_instagram_task_handler(*, device, device_id: str = "") -> WorkflowHandler:
    """Build an injectable Instagram task handler without bridge startup."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        merged = _merge_invocation_payload(invocation, payload)

        if invocation.workflow_id == INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID:
            return relay_source_stories(
                device=device,
                source_username=_source_username(merged),
                account_id=_optional_int(merged, "account_id", "accountId"),
                max_stories=_int_param(merged, "max_stories", "maxStories",
                                       default=DEFAULT_MAX_STORIES),
            )

        raise ValueError(f"Unsupported Instagram task workflow id: {invocation.workflow_id}")

    return handler


def register_instagram_task_handlers(
    registry: WorkflowRegistry,
    *,
    device,
    device_id: str = "",
) -> WorkflowRegistry:
    """Register Instagram task handlers into an injected Agent registry."""
    handler = build_instagram_task_handler(device=device, device_id=device_id)
    for workflow_id in INSTAGRAM_TASK_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _merge_invocation_payload(
    invocation: WorkflowInvocation,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(payload)
    merged.update(invocation.params)
    return merged


def _source_username(payload: Mapping[str, Any]) -> str:
    """The account whose stories are relayed — never the one doing the relaying."""
    for key in ("source_username", "sourceUsername"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lstrip("@")
    raise ValueError("Instagram story relay requires source_username")


def _optional_int(payload: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _int_param(payload: Mapping[str, Any], *keys: str, default: int) -> int:
    value = _optional_int(payload, *keys)
    return default if value is None else value


__all__ = [
    "INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID",
    "INSTAGRAM_TASK_WORKFLOW_IDS",
    "build_instagram_task_handler",
    "register_instagram_task_handlers",
]
