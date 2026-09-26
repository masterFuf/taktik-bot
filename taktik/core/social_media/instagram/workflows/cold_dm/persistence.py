"""Sent-DM persistence for the Instagram Cold DM workflow."""

from __future__ import annotations

from taktik.core.database.messaging import SentDMService


def check_dm_already_sent(account_id: int, recipient_username: str) -> bool:
    """Check if a DM was already sent to this recipient on Instagram."""
    return SentDMService.check_already_sent(account_id, recipient_username, platform="instagram")


def record_sent_dm(
    account_id: int,
    recipient_username: str,
    message: str,
    success: bool,
    error_message: str = None,
    session_id: str = None,
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
