"""TikTok unfollow workflow-test runner."""

from loguru import logger


def run_tiktok_unfollow(conn, device, ipc, limits):
    """Run TikTok unfollow workflow."""
    try:
        from taktik.core.social_media.tiktok.workflows.unfollow import UnfollowWorkflow

        max_unfollows = limits.get("maxUnfollows", 20)

        ipc.send("workflow_step", step="tiktok_unfollow", status="running")
        wf = UnfollowWorkflow(device)
        success = wf.run(max_unfollows=max_unfollows)
        ipc.send("workflow_step", step="tiktok_unfollow", status="done" if success else "failed")
        return success
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok unfollow failed: {exc}")
        ipc.send("workflow_step", step="tiktok_unfollow", status="error", error=str(exc))
        return False
