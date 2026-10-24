"""Sent-DM persistence for the Instagram Cold DM workflow."""

from __future__ import annotations

from typing import Optional

from taktik.core.database.messaging import SentDMService


def check_dm_already_sent(account_id: int, recipient_username: str) -> bool:
    """Check if a DM was already sent to this recipient on Instagram."""
    return SentDMService.check_already_sent(account_id, recipient_username, platform="instagram")


def record_pending_dm(account_id: int, recipient_username: str, message: str,
                      session_id: Optional[str] = None) -> None:
    """Record an Instagram DM the conversation showed waiting to be sent (`sent_dms`, not a success)."""
    SentDMService.record_pending(account_id, recipient_username, message, session_id, platform="instagram")


def record_sent_dm(
    account_id: int,
    recipient_username: str,
    message: str,
    success: bool,
    error_message: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Record a sent Instagram DM (`sent_dms`)."""
    SentDMService.record(
        account_id,
        recipient_username,
        message,
        success,
        error_message,
        session_id,
        platform="instagram",
    )
