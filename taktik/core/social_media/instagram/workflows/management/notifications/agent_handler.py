"""The one launcher of an Instagram notifications run, and its Agent handler.

`run_instagram_notifications` runs one command of the activity feed: `scan`, `list_requests`,
`accept_all`, a row verb (`accept`, `ignore`, `like`, `follow_back`, `reply`) or a `batch`. The
desktop bridge (`notifications_bridge <config.json>`) calls it, and so does the handler registered
as `instagram.engagement.notifications` (the CLI). What differs between the hosts is injected:
- `connect(restart) -> runtime`: the connected device (`device`, `device_id`,
  `restart_instagram()`, `stop()`), Instagram restarted first when `restart` is true;
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
from taktik.core.social_media.instagram.workflows.management.notifications import commands


INSTAGRAM_NOTIFICATIONS_WORKFLOW_ID = "instagram.engagement.notifications"

Connect = Callable[[bool], Any]
Emit = Callable[[dict], None]
AIServiceFactory = Callable[[Mapping[str, Any]], Any]
RuntimeProvider = Callable[[Optional[str], bool], Any]

_NEEDS_USERNAME = (*commands.ROW_ACTIONS, "reply")
NOTIFICATIONS_COMMANDS = ("scan", "list_requests", "accept_all", "reply", "batch", *commands.ROW_ACTIONS)


class NotificationsCommandError(ValueError):
    """The command is refused before the phone is touched."""


def _count(value, default):
    """A count as written, `default` when absent."""
    return default if value is None else int(value)


def _cap(value):
    """A daily cap: None (uncapped) when absent or unreadable, never below 0."""
    try:
        return None if value is None else max(0, int(value))
    except (TypeError, ValueError):
        return None


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

    The payload: `{"command", "accountUsername"?}` plus, per command,
    `scroll`, `followSuggestions`, `ai` and `language` (scan), `limit` (list_requests), `max`
    (accept_all), `username` (accept, ignore, like, follow_back, reply), `text` (reply), and
    `actions`, `source`, `followBackDailyCap`, `welcomeDmDailyCap`, `followActorDailyCap` (batch).
    `deviceId` and `packageName` are the host's, read when it connects.
    """
    command = config.get("command")
    # The owning account (the desktop resolves it from the device): `scan` persists and
    # dedups under it (the activity screen has no header), every action records under it.
    account_username = config.get("accountUsername")
    username = config.get("username")

    if command not in NOTIFICATIONS_COMMANDS:
        raise NotificationsCommandError(f"Unknown command: {command}")
    if command in _NEEDS_USERNAME and not username:
        raise NotificationsCommandError(f"username is required for {command}")

    host = commands.NotificationsHost(connect=connect, emit=emit or _log_event,
                                      ai_service=instagram_ai_service)

    if command == "scan":
        # Opt-in suggestions visit at the end of the scan; `ai` qualifies the visited
        # profiles (same block as the automation's), `language` is the AI's wording.
        try:
            follow_suggestions = max(0, int(config.get("followSuggestions") or 0))
        except (TypeError, ValueError):
            follow_suggestions = 0
        ai_config = config.get("ai")
        if ai_config is not None and not isinstance(ai_config, dict):
            logger.warning("[NOTIF] Unreadable ai config: AI qualification off")
            ai_config = None
        return commands.cmd_scan(host, _count(config.get("scroll"), 3),
                                 follow_suggestions=follow_suggestions,
                                 account_username=account_username,
                                 ai_config=ai_config, language=config.get("language") or "en")

    if command == "list_requests":
        return commands.cmd_list_requests(host, _count(config.get("limit"), 50))

    if command == "accept_all":
        return commands.cmd_accept_all(host, _count(config.get("max"), 50),
                                       account_username=account_username)

    if command == "reply":
        return commands.cmd_reply(host, username, config.get("text") or "",
                                  account_username=account_username)

    if command == "batch":
        actions = config.get("actions")
        if not isinstance(actions, list) or not actions:
            raise NotificationsCommandError("Batch actions must be a non-empty list")
        # 'autopilot' marks a batch a policy triggered, recorded in notification_actions.
        # The daily caps are enforced here against the audit table; absent = uncapped,
        # which is what an operator's own selection is.
        return commands.cmd_batch(host, actions, account_username=account_username,
                                  source=(config.get("source") or "batch").strip() or "batch",
                                  follow_back_daily_cap=_cap(config.get("followBackDailyCap")),
                                  welcome_dm_daily_cap=_cap(config.get("welcomeDmDailyCap")),
                                  follow_actor_daily_cap=_cap(config.get("followActorDailyCap")))

    return commands.ROW_ACTIONS[command](host, username, account_username=account_username)


def build_instagram_notifications_handler(
    *,
    instagram_notifications_runtime: Optional[RuntimeProvider] = None,
    instagram_ai_service: Optional[AIServiceFactory] = None,
) -> WorkflowHandler:
    """Build an injectable notifications handler: the launcher, on the runtime the host prepares."""

    def handler(invocation: WorkflowInvocation, payload: dict[str, Any]) -> dict[str, Any]:
        if instagram_notifications_runtime is None:
            raise RuntimeError("Instagram notifications need a connected device")
        config = dict(payload)
        config.update(invocation.params)
        config.setdefault("command", "scan")
        package_name = config.get("packageName")
        return run_instagram_notifications(
            config,
            connect=lambda restart: instagram_notifications_runtime(package_name, restart),
            instagram_ai_service=instagram_ai_service,
        )

    return handler


def register_instagram_notifications_handlers(
    registry: WorkflowRegistry,
    *,
    instagram_notifications_runtime: Optional[RuntimeProvider] = None,
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
