"""TikTok publish workflow-test runner."""

from loguru import logger


def run_tiktok_publish(conn, device, ipc):
    """Run TikTok publish navigation test."""
    try:
        from taktik.core.social_media.tiktok.publish.navigator import TikTokPublishNavigator

        ipc.send("workflow_step", step="tiktok_upload_navigate", status="running")
        navigator = TikTokPublishNavigator(device)
        can_navigate = navigator.navigate_to_upload()
        ipc.send("workflow_step", step="tiktok_upload_navigate", status="done" if can_navigate else "failed")
        try:
            navigator.go_back()
        except Exception:
            pass
        return can_navigate
    except Exception as exc:
        logger.exception(f"[WorkflowTest] TikTok publish failed: {exc}")
        ipc.send("workflow_step", step="tiktok_upload", status="error", error=str(exc))
        return False
