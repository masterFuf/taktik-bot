"""An account's health history: one entry per block the platform put on it.

The run's stop latch (`shared/diagnostics/run_halt.py`) is set by whoever SEES the block: a probe
after a gesture, the popup handler during a navigation, a list walk. None of them knows which
account is operated. The platform runtime that does know installs `witness_for(...)` on the latch,
and the first halt of the run becomes one row of `account_restriction_signals` with the signal
`action_blocked`, next to the `private_first_ordering` rows the followers walk already writes.

One row per blocked run, not per sighting: the latch keeps only its first reading, so the witness
is told once. Written through the repository, never raises.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from loguru import logger

#: The halt code this history keeps; the other codes (lost phone, crashed app, desktop gone) say
#: nothing about the account.
ACTION_BLOCKED = "action_blocked"


def record_action_block(
    halt: Optional[Dict[str, Any]],
    *,
    platform: str,
    account_username: Optional[str],
    source_type: Optional[str] = None,
    session_id: Optional[int] = None,
) -> bool:
    """Write one `action_blocked` signal for `account_username` when `halt` is a block."""
    if not halt or halt.get("code") != ACTION_BLOCKED:
        return False
    account = (account_username or "").strip().lstrip("@")
    if not account or account == "unknown":
        logger.warning("Block seen before the operated account was known: not kept in its history")
        return False
    try:
        from taktik.core.database.local.service import get_local_database

        return bool(get_local_database().account_restrictions.record_signal(
            account,
            platform=platform,
            signal=ACTION_BLOCKED,
            source_type=source_type,
            session_id=session_id,
        ))
    except Exception as exc:  # noqa: BLE001 - losing a measurement must not lose the run
        logger.debug(f"Could not record the block in the account's history: {exc}")
        return False


def witness_for(
    platform: str,
    account: Callable[[], Optional[str]],
    *,
    source_type: Callable[[], Optional[str]] = lambda: None,
    session_id: Callable[[], Optional[int]] = lambda: None,
) -> Callable[[Dict[str, Any]], None]:
    """The listener to install on the run's latch (`run_halt.configurer_temoin`).

    Takes readers rather than values: the account and the session are often resolved after the
    listener is installed, and are read when the block happens.
    """
    def _witness(halt: Dict[str, Any]) -> None:
        record_action_block(
            halt,
            platform=platform,
            account_username=account(),
            source_type=source_type(),
            session_id=session_id(),
        )

    return _witness


__all__ = ["ACTION_BLOCKED", "record_action_block", "witness_for"]
