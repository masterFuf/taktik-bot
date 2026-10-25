"""Send-result handling for the Instagram Cold DM workflow."""

from __future__ import annotations

from taktik.core.shared.diagnostics import run_halt
from taktik.core.social_media.instagram.workflows.cold_dm.persistence import record_pending_dm, record_sent_dm
from taktik.core.social_media.instagram.workflows.dm.messaging import INVITE_ALREADY_SENT
from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome
from loguru import logger


def validate_cold_dm_inputs(*, recipients: list, messages: list, use_ai: bool) -> dict | None:
    """Return a terminal error result when the run's input cannot run."""
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
    """Build the final Cold DM result payload from workflow counters.

    A run stopped by the halt latch says why (`stop_reason`: `action_blocked` when Instagram
    refused a send), so it does not read as a run that went through its list.
    """
    summary = {
        "success": True,
        "dms_sent": workflow.dms_sent,
        "dms_success": workflow.dms_success,
        "dms_failed": workflow.dms_failed,
        "dms_pending": workflow.dms_pending,
        "private_profiles": workflow.private_profiles,
        "verified_profiles": getattr(workflow, "verified_profiles", 0),
        "texts_refused": workflow.texts_refused,
    }
    halt = run_halt.arret_demande()
    if halt:
        summary["stop_reason"] = halt.get("code")
    return summary


def apply_cold_dm_send_result(
    *,
    workflow,
    recipient: str,
    message: str,
    send_result,
    account_id: int,
    session_id: str | None,
) -> None:
    if send_result == INVITE_ALREADY_SENT:
        logger.info(f"Invite already sent to {recipient} - marking as done")
        record_sent_dm(account_id, recipient, "", True, "Invite already sent", session_id)
        workflow.dms_sent += 1
    elif send_result is ReplyOutcome.SENT:
        workflow.dms_success += 1
        logger.info(f"Successfully sent DM to {recipient}")
        record_sent_dm(account_id, recipient, message, True, None, session_id)
        workflow.dms_sent += 1
    elif send_result is ReplyOutcome.PENDING:
        # In the conversation, waiting for the network: it leaves by itself. Not counted as sent,
        # and its marker keeps it from being sent again (`SentDMService.record_pending`).
        workflow.dms_pending += 1
        logger.warning(f"DM to {recipient} waiting to be sent: not counted, not sent again")
        record_pending_dm(account_id, recipient, message, session_id)
    else:
        workflow.dms_failed += 1
        logger.warning(f"Failed to send DM to {recipient}")


__all__ = [
    "apply_cold_dm_send_result",
    "build_all_recipients_processed_result",
    "build_cold_dm_summary",
    "validate_cold_dm_inputs",
]
