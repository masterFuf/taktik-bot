"""Send-result handling for the Instagram Cold DM bridge."""

from __future__ import annotations

from bridges.instagram.engagement.runtime.cold_dm.persistence import record_sent_dm
from bridges.instagram.runtime.ipc import logger


def apply_cold_dm_send_result(
    *,
    workflow,
    recipient: str,
    message: str,
    send_result,
    account_id: int,
    session_id: str | None,
) -> None:
    if send_result == "invite_sent":
        logger.info(f"Invite already sent to {recipient} - marking as done")
        record_sent_dm(account_id, recipient, "", True, "Invite already sent", session_id)
        workflow.dms_sent += 1
    elif send_result:
        workflow.dms_success += 1
        logger.info(f"Successfully sent DM to {recipient}")
        record_sent_dm(account_id, recipient, message, True, None, session_id)
        workflow.dms_sent += 1
    else:
        workflow.dms_failed += 1
        logger.warning(f"Failed to send DM to {recipient}")
