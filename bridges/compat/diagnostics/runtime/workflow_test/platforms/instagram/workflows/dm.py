"""Instagram DM workflow-test runners."""

from loguru import logger


def run_instagram_dm(conn, device, ipc, workflow_type, limits, delays):
    """Run an Instagram DM workflow."""
    try:
        max_dms = limits.get("maxDMs", 10)

        if workflow_type == "dm_response":
            from taktik.core.social_media.instagram.engagement.dm.reader import DMReader

            ipc.send("workflow_step", step="dm_read", status="running")
            reader = DMReader(device)
            conversations = reader.read_conversations(max_conversations=max_dms)
            count = len(conversations) if conversations else 0
            ipc.send("workflow_step", step="dm_read", status="done")
            ipc.send(
                "action_event",
                action="dm_read_complete",
                username="",
                success=count > 0,
                data={"conversations": count},
            )
            return count > 0

        if workflow_type == "dm_outreach":
            from taktik.core.social_media.instagram.engagement.dm.outreach import DMOutreach

            ipc.send("workflow_step", step="dm_outreach", status="running")
            outreach = DMOutreach(device)
            sent = outreach.send_batch(max_dms=max_dms)
            ipc.send("workflow_step", step="dm_outreach", status="done")
            ipc.send(
                "action_event",
                action="dm_outreach_complete",
                username="",
                success=sent > 0,
                data={"sent": sent},
            )
            return sent > 0

        return False
    except Exception as exc:
        logger.exception(f"[WorkflowTest] DM workflow failed: {exc}")
        ipc.send("workflow_step", step=workflow_type, status="error", error=str(exc))
        return False
