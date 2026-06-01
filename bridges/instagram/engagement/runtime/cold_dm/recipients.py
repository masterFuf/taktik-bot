"""Recipient filtering helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

from bridges.instagram.engagement.runtime.cold_dm.persistence import check_dm_already_sent
from bridges.instagram.runtime.ipc import logger


class ColdDMRecipientMixin:
    """Filter outreach recipients before the send loop."""

    def filter_pending_recipients(self, recipients: list, account_id: int) -> list:
        filtered_recipients = []
        skipped_count = 0

        for recipient in recipients:
            if check_dm_already_sent(account_id, recipient):
                logger.info(f"Skipping {recipient} - DM already sent")
                skipped_count += 1
            else:
                filtered_recipients.append(recipient)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} recipients (DM already sent)")

        return filtered_recipients
