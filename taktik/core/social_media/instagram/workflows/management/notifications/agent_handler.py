"""The one launcher of an Instagram notifications run, and its Agent handler.

`run_instagram_notifications` runs one command of the activity feed: `scan`, `list_requests`,
`accept_all`, a row verb (`accept`, `ignore`, `like`, `follow_back`, `reply`) or a `batch`. The
desktop bridge (`notifications_bridge <config.json>`) calls it, and so does the handler registered
as `instagram.engagement.notifications` (the CLI). What differs between the hosts is injected:
- `connect(package_name, restart) -> runtime`: the connected device (`device`, `device_id`,
  `restart_instagram()`, `stop()`), on the Instagram the payload names (`packageName`, a clone;
  None: the installed one), Instagram restarted first when `restart` is true;
- `emit(payload)`: the run's events (the bridge's stdout, the CLI's log);
- `instagram_ai_service(ai_config) -> service | None`: qualifies the profiles a scan visits.
No injected callable receives the whole payload, so the app's config contract test can still see
every key the bot reads.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

from taktik.core.agent.kernel.contracts import WorkflowInvocation
from taktik.core.agent.kernel.registry import WorkflowHandler, WorkflowRegistry
from taktik.core.social_media.instagram.workflows.core.startup import package_name_from_payload
from taktik.core.social_media.instagram.workflows.management.notifications import commands
from taktik.core.social_media.instagram.workflows.management.notifications.payload import (
    NOTIFICATIONS_COMMANDS,
    NotificationsCommandError,
    notifications_request_from_payload,
)


INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID = "instagram.engagement.notifications"

Connect = Callable[[Optional[str], bool], Any]
Emit = Callable[[dict], None]
AIServiceFactory = Callable[[Mapping[str, Any]], Any]


def _log_event(payload: Mapping[str, Any]) -> None:
    # Never a message body: the step and its narration only.
    logger.info(f"[NOTIF] {payload.get('step', payload.get('type', 'event'))}: {payload.get('message', '')}")


def run_instagram_notifications(
    config: Mapping[str, Any],
    *,
    connect: Connect,
    emit: Optional[Emit] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
) -> dict[str, Any]:
    """Run the notifications command a payload describes; return the result the desktop reads.

    The payload is read by `notifications_request_from_payload` (`payload.py`), which refuses
    an unknown command, a row verb or a reply without `username` and a batch without actions,
    before the phone is touched. `deviceId` is the host's, read when it connects; `packageName`
    is read here and handed to it.
    """
    request = notifications_request_from_payload(config)
    package_name = package_name_from_payload(config)
    host = commands.NotificationsHost(connect=lambda restart: connect(package_name, restart),
                                      emit=emit or _log_event, ai_service=instagram_ai_service)
    account_username = request.account_username

    if request.command == "scan":
        return commands.cmd_scan(host, request.scroll,
                                 follow_suggestions=request.follow_suggestions,
                                 account_username=account_username,
                                 ai_config=request.ai, language=request.language)
    if request.command == "list_requests":
        return commands.cmd_list_requests(host, request.limit)
    if request.command == "accept_all":
        return commands.cmd_accept_all(host, request.accept_max, account_username=account_username)
    if request.command == "reply":
        return commands.cmd_reply(host, request.username, request.text,
                                  account_username=account_username)
    if request.command == "batch":
        # The daily caps are enforced here against the audit table.
        return commands.cmd_batch(host, request.actions, account_username=account_username,
                                  source=request.source,
                                  follow_back_daily_cap=request.follow_back_daily_cap,
                                  welcome_dm_daily_cap=request.welcome_dm_daily_cap,
                                  follow_actor_daily_cap=request.follow_actor_daily_cap)
    return commands.ROW_ACTIONS[request.command](host, request.username, account_username=account_username)


def build_instagram_notifications_handler(
    *,
    instagram_notifications_runtime: Optional[Connect] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
) -> WorkflowHandler:
    """Build an injectable notifications handler: the launcher, on the runtime the host prepares."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_notifications_runtime is None:
            raise RuntimeError("Instagram notifications need a connected device")
        config = dict(payload)
        config.update(invocation.params)
        config.setdefault("command", "scan")
        return run_instagram_notifications(
            config,
            connect=instagram_notifications_runtime,
            instagram_ai_service=instagram_ai_service,
        )

    return handler


def register_instagram_notifications_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_notifications_runtime: Optional[Connect] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
) -> WorkflowRegistry:
    """Register the Instagram notifications handler into an injected Agent registry."""
    registry.register(
        INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID,
        build_instagram_notifications_handler(
            instagram_notifications_runtime=instagram_notifications_runtime,
            instagram_ai_service=instagram_ai_service,
        ),
    )
    return registry


__all__ = [
    "INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID",
    "NOTIFICATIONS_COMMANDS",
    "NotificationsCommandError",
    "build_instagram_notifications_handler",
    "register_instagram_notifications_handlers",
    "run_instagram_notifications",
]
