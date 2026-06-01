"""Send-result handling for the Instagram Cold DM bridge."""

from __future__ import annotations

from bridges.instagram.engagement.runtime.cold_dm.persistence import record_sent_dm
from bridges.instagram.runtime.ipc import logger


def validate_cold_dm_inputs(*, recipients: list, messages: list, use_ai: bool) -> dict | None:
    """Return a terminal error result when the bridge input cannot run."""
    if not messages and not use_ai:
        return {"success": False, "error": "No messages provided and AI mode not configured"}

    if not recipients:
        return {"success": False, "error": "No recipients provided"}

    return None


def build_all_recipients_processed_result() -> dict:
    """Return the historical success payload when every recipient is already done."""
    return {
        "success": True,
        "dms_sent": 0,
        "dms_success": 0,
        "dms_failed": 0,
        "error": "All recipients already received a DM",
    }


def build_cold_dm_summary(workflow) -> dict:
    """Build the final Cold DM result payload from workflow counters."""
    return {
        "success": True,
        "dms_sent": workflow.dms_sent,
        "dms_success": workflow.dms_success,
        "dms_failed": workflow.dms_failed,
        "private_profiles": workflow.private_profiles,
    }


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


__all__ = [
    "apply_cold_dm_send_result",
    "build_all_recipients_processed_result",
    "build_cold_dm_summary",
    "validate_cold_dm_inputs",
]
