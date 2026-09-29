"""What an Instagram notifications run reads of its payload: one command and its values.

`run_instagram_notifications`, the one launcher the desktop bridge and the handler of
`instagram.engagement.notifications` (the CLI) call, reads its payload here and nowhere else.
The keys, their defaults and the refusals are declared in `taktik/core/contract/`, the
source of the app's types; `tests/unit/app/contract` holds this reader to it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional

from loguru import logger

#: The commands that act on the row of one account.
ROW_COMMANDS = ("accept", "ignore", "like", "follow_back")
NOTIFICATIONS_COMMANDS = ("scan", "list_requests", "accept_all", "reply", "batch", *ROW_COMMANDS)
NEEDS_USERNAME = (*ROW_COMMANDS, "reply")


class NotificationsCommandError(ValueError):
    """The command is refused before the phone is touched."""


@dataclass(frozen=True)
class NotificationsRequest:
    """One command and the values it runs with; a value another command reads keeps its default."""

    command: str
    account_username: Optional[str] = None
    username: Optional[str] = None
    scroll: int = 3
    follow_suggestions: int = 0
    ai: Optional[Dict[str, Any]] = None
    language: str = "en"
    limit: int = 50
    accept_max: int = 50
    text: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "batch"
    follow_back_daily_cap: Optional[int] = None
    welcome_dm_daily_cap: Optional[int] = None
    follow_actor_daily_cap: Optional[int] = None


def _count(value, default):
    """A count as written, `default` when absent."""
    return default if value is None else int(value)


def _cap(value):
    """A daily cap: None (uncapped) when absent or unreadable, never below 0."""
    try:
        return None if value is None else max(0, int(value))
    except (TypeError, ValueError):
        return None


def notifications_request_from_payload(payload: Mapping[str, Any]) -> NotificationsRequest:
    """The command `payload` describes; `NotificationsCommandError` when it cannot run.

    `accountUsername` is the owning account (the desktop resolves it from the device): `scan`
    persists and dedups under it (the activity screen has no header), every action records
    under it. Each other key is read for the command that uses it only.
    """
    command = payload.get("command")
    if command not in NOTIFICATIONS_COMMANDS:
        raise NotificationsCommandError(f"Unknown command: {command}")
    values: Dict[str, Any] = {"command": command, "account_username": payload.get("accountUsername")}

    if command in NEEDS_USERNAME:
        username = payload.get("username")
        if not username:
            raise NotificationsCommandError(f"username is required for {command}")
        values["username"] = username

    if command == "scan":
        # Opt-in suggestions visit at the end of the scan; `ai` qualifies the visited
        # profiles (same block as the automation's), `language` is the AI's wording.
        try:
            values["follow_suggestions"] = max(0, int(payload.get("followSuggestions") or 0))
        except (TypeError, ValueError):
            values["follow_suggestions"] = 0
        ai_config = payload.get("ai")
        if ai_config is not None and not isinstance(ai_config, dict):
            logger.warning("[NOTIF] Unreadable ai config: AI qualification off")
            ai_config = None
        values.update(scroll=_count(payload.get("scroll"), 3), ai=ai_config,
                      language=payload.get("language") or "en")
    elif command == "list_requests":
        values["limit"] = _count(payload.get("limit"), 50)
    elif command == "accept_all":
        values["accept_max"] = _count(payload.get("max"), 50)
    elif command == "reply":
        values["text"] = payload.get("text") or ""
    elif command == "batch":
        actions = payload.get("actions")
        if not isinstance(actions, list) or not actions:
            raise NotificationsCommandError("Batch actions must be a non-empty list")
        # 'autopilot' marks a batch a policy triggered, recorded in notification_actions.
        # Absent caps = uncapped, which is what an operator's own selection is.
        values.update(actions=list(actions),
                      source=(payload.get("source") or "batch").strip() or "batch",
                      follow_back_daily_cap=_cap(payload.get("followBackDailyCap")),
                      welcome_dm_daily_cap=_cap(payload.get("welcomeDmDailyCap")),
                      follow_actor_daily_cap=_cap(payload.get("followActorDailyCap")))
    return NotificationsRequest(**values)


__all__ = [
    "NEEDS_USERNAME",
    "NOTIFICATIONS_COMMANDS",
    "NotificationsCommandError",
    "NotificationsRequest",
    "ROW_COMMANDS",
    "notifications_request_from_payload",
]
