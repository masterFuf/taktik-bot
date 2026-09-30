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

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.kernel.contracts import WorkflowInvocation
from taktik.core.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.common.startup import InstagramStartError, package_name_from_payload
from taktik.core.social_media.instagram.workflows.tasks.story_relay import (
    DEFAULT_MAX_STORIES,
    INSTAGRAM_LAUNCH_FAILED,
    new_relay_report,
    relay_source_stories,
)

INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID = "instagram.task.story_relay"
INSTAGRAM_TASK_WORKFLOW_IDS = (INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID,)

#: `connect(package_name) -> device`: the phone after a clean restart of the Instagram the payload
#: names (a clone; None: the installed one), so a task starts from the feed. Raises
#: `InstagramStartError` when that Instagram did not restart.
Connect = Callable[[Optional[str]], Any]


@dataclass(frozen=True)
class StoryRelayRequest:
    """What one story relay pass is asked, read once from its payload."""

    source_username: str
    account_id: Optional[int] = None
    max_stories: int = DEFAULT_MAX_STORIES


def story_relay_request_from_payload(payload: Mapping[str, Any]) -> StoryRelayRequest:
    """The story relay settings, as the page, the scheduler and the CLI send them. Refuses a
    payload without a source account, before the phone is touched."""
    return StoryRelayRequest(
        source_username=_source_username(payload),
        account_id=_optional_int(payload, "account_id", "accountId"),
        max_stories=_int_param(payload, "max_stories", "maxStories", default=DEFAULT_MAX_STORIES),
    )


def run_instagram_story_relay(
    payload: Mapping[str, Any],
    *,
    connect: Connect,
    relay: Callable[..., dict[str, Any]] = relay_source_stories,
) -> dict[str, Any]:
    """The one launcher of the story relay: read the payload, then run one pass on the phone the host
    connects, on the payload's Instagram. An Instagram that did not restart stops the pass before the
    relay, with its reason: the relay would read whatever screen the phone was left on."""
    request = story_relay_request_from_payload(payload)
    try:
        device = connect(package_name_from_payload(payload))
    except InstagramStartError as exc:
        logger.error(f"Story relay stopped before it started: {exc}")
        report = new_relay_report(request.source_username)
        report["reason"] = INSTAGRAM_LAUNCH_FAILED
        return report
    return relay(
        device=device,
        source_username=request.source_username,
        account_id=request.account_id,
        max_stories=request.max_stories,
    )


def build_instagram_task_handler(*, instagram_task_connect: Optional[Connect] = None) -> WorkflowHandler:
    """Build an injectable Instagram task handler: the launcher, on the host's connection."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_task_connect is None:
            raise RuntimeError("An Instagram task needs a connected device")
        merged = _merge_invocation_payload(invocation, payload)

        if invocation.workflow_id == INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID:
            return run_instagram_story_relay(merged, connect=instagram_task_connect)

        raise ValueError(f"Unsupported Instagram task workflow id: {invocation.workflow_id}")

    return handler


def register_instagram_task_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_task_connect: Optional[Connect] = None,
) -> WorkflowRegistry:
    """Register Instagram task handlers into an injected Agent registry."""
    handler = build_instagram_task_handler(instagram_task_connect=instagram_task_connect)
    for workflow_id in INSTAGRAM_TASK_WORKFLOW_IDS:
        registry.register(workflow_id, handler)
    return registry


def _merge_invocation_payload(
    invocation: WorkflowInvocation,
    payload: Mapping[str, Any],
) -> Mapping[str, Any]:
    if not invocation.params:
        return payload
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
    "StoryRelayRequest",
    "build_instagram_task_handler",
    "register_instagram_task_handlers",
    "run_instagram_story_relay",
    "story_relay_request_from_payload",
]
