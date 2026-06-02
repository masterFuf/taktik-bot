"""Instagram Smart Comment workflow-test runner."""

from loguru import logger


def run_instagram_smart_comment(conn, device, ipc, target, limits, delays):
    """Run an Instagram Smart Comment workflow."""
    try:
        from taktik.core.social_media.instagram.engagement.smart_comment.engine import SmartCommentEngine

        max_comments = limits.get("maxComments", 5)

        ipc.send("workflow_step", step="smart_comment_scrape", status="running")
        engine = SmartCommentEngine(device)
        result = engine.run(
            target_username=target if target else None,
            max_comments=max_comments,
        )
        success = result.get("success", False) if isinstance(result, dict) else bool(result)
        ipc.send("workflow_step", step="smart_comment_scrape", status="done" if success else "failed")
        ipc.send(
            "action_event",
            action="smart_comment_complete",
            username=target or "",
            success=success,
            data={"max_comments": max_comments},
        )
        return success
    except Exception as exc:
        logger.exception(f"[WorkflowTest] Smart comment failed: {exc}")
        ipc.send("workflow_step", step="smart_comment", status="error", error=str(exc))
        return False
