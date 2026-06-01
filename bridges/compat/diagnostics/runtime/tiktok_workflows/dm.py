"""TikTok DM workflow-test runners."""

from loguru import logger


def run_tiktok_dm(conn, device, ipc, workflow_type, limits):
    """Run a TikTok DM workflow."""
    try:
        max_dms = limits.get("maxDMs", 10)

        if workflow_type == "dm_read":
            from taktik.core.social_media.tiktok.engagement.dm.reader import TikTokDMReader

            ipc.send("workflow_step", step="tiktok_dm_read", status="running")
            reader = TikTokDMReader(device)
            conversations = reader.read_conversations(max_conversations=max_dms)
            count = len(conversations) if conversations else 0
            ipc.send("workflow_step", step="tiktok_dm_read", status="done")
            ipc.send(
                "action_event",
                action="tiktok_dm_read_complete",
                username="",
                success=count > 0,
                data={"conversations": count},
            )
            return count > 0

        if workflow_type == "dm_outreach":
            from taktik.core.social_media.tiktok.engagement.dm.outreach import TikTokDMOutreach

            ipc.send("workflow_step", step="tiktok_dm_outreach", status="running")
            outreach = TikTokDMOutreach(device)
            sent = outreach.send_batch(max_dms=max_dms)
            ipc.send("workflow_step", step="tiktok_dm_outreach", status="done")
            ipc.send(
                "action_event",
                action="tiktok_dm_outreach_complete",
                username="",
                success=sent > 0,
                data={"sent": sent},
            )
            return sent > 0

        return False
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok DM failed: {exc}")
        ipc.send("workflow_step", step=f"tiktok_{workflow_type}", status="error", error=str(exc))
        return False
