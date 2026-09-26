"""The session a cold DM run is filed under.

Same lifecycle as an automation run: `create_session` when the run starts, `session_start` for the
desktop (which writes the run's AI spend into the row), `finalize_session` when it ends. Without a
known account no session is opened: filing the run under another account would be worse than
filing it nowhere.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from loguru import logger

from taktik.core.social_media.instagram.workflows.management.session import stop_reasons


COLD_DM_WORKFLOW_TYPE = "cold_dm"
COLD_DM_TARGET_TYPE = "DM"

STATUS_COMPLETED = "COMPLETED"
STATUS_ERROR = "ERROR"
STATUS_STOPPED = "STOPPED"

log = logger.bind(module="instagram-cold-dm-session")


def recipients_summary(recipients: Sequence[Any]) -> str:
    """`@first (+N)`: who the run writes to, in the room a session target has."""
    names = [str(name).strip().lstrip("@") for name in recipients or []]
    names = [name for name in names if name]
    if not names:
        return ""
    more = f" (+{len(names) - 1})" if len(names) > 1 else ""
    return f"@{names[0]}{more}"


def session_account_id(config: Mapping[str, Any]) -> Optional[int]:
    """The account the run's session belongs to.

    `sessionAccountId` is the account the desktop saw on the phone. `accountId` keys the
    duplicate check of `sent_dms` and is used only when the caller gave it explicitly.
    """
    return _positive_int(config.get("sessionAccountId")) or _positive_int(config.get("accountId"))


def _positive_int(value: Any) -> Optional[int]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def open_cold_dm_session(account_id: Optional[int], *, recipients: Sequence[Any],
                         config: Optional[Mapping[str, Any]] = None) -> Optional[int]:
    """Open the run's session and return its id, or None when there is none. Never raises."""
    if not account_id:
        log.warning("No account known for this cold DM run: no session is opened")
        return None
    target = recipients_summary(recipients)
    try:
        from taktik.core.database.local.service import get_local_database

        session_id = get_local_database().create_session(
            account_id=account_id,
            session_name=f"{COLD_DM_WORKFLOW_TYPE} - {target}" if target else COLD_DM_WORKFLOW_TYPE,
            target_type=COLD_DM_TARGET_TYPE,
            target=target,
            config_used=dict(config) if config else None,
            workflow_type=COLD_DM_WORKFLOW_TYPE,
        )
    except Exception as exc:  # noqa: BLE001 - the run goes on without a session
        log.warning(f"Cold DM session not opened: {exc}")
        return None
    if session_id:
        log.info(f"Cold DM session {session_id} opened")
    return session_id or None


def outcome_of(result: Optional[Mapping[str, Any]] = None,
               error: Optional[BaseException] = None) -> tuple[str, Any, Optional[str]]:
    """(status, stop reason, error message) of a run that returned `result` or raised `error`."""
    if error is not None:
        if isinstance(error, Exception):
            return STATUS_ERROR, stop_reasons.crashed(error), None
        return STATUS_STOPPED, stop_reasons.manual_stop(), None
    result = result or {}
    if result.get("success"):
        return STATUS_COMPLETED, stop_reasons.completed(int(result.get("dms_sent") or 0)), None
    message = str(result.get("error") or "Cold DM run failed")[:500]
    return STATUS_ERROR, None, message


def close_cold_dm_session(session_id: Optional[int], *, duration_seconds: int,
                          result: Optional[Mapping[str, Any]] = None,
                          error: Optional[BaseException] = None) -> None:
    """Close the session with its status, duration and stop reason. Never raises."""
    if not session_id:
        return
    status, reason, message = outcome_of(result, error)
    try:
        from taktik.core.database.local.service import get_local_database

        get_local_database().finalize_session(
            session_id, status,
            duration_seconds=duration_seconds,
            error_message=message,
            stop_reason=reason,
        )
        log.info(f"Cold DM session {session_id} closed ({status})")
    except Exception as exc:  # noqa: BLE001
        log.warning(f"Cold DM session {session_id} not closed: {exc}")


__all__ = [
    "COLD_DM_TARGET_TYPE",
    "COLD_DM_WORKFLOW_TYPE",
    "close_cold_dm_session",
    "open_cold_dm_session",
    "outcome_of",
    "recipients_summary",
    "session_account_id",
]
