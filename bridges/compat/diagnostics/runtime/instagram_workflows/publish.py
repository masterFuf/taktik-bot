"""Instagram publish workflow-test runner."""

from loguru import logger


def run_instagram_publish(conn, device, ipc, workflow_type):
    """Run an Instagram publish navigation test."""
    try:
        from taktik.core.social_media.instagram.publish.navigator import PublishNavigator

        upload_type_map = {
            "upload_post": "post",
            "upload_carousel": "carousel",
            "upload_reel": "reel",
            "upload_story": "story",
        }
        upload_type = upload_type_map.get(workflow_type, "post")

        ipc.send("workflow_step", step=f"publish_navigate_{upload_type}", status="running")
        navigator = PublishNavigator(device)
        can_navigate = navigator.navigate_to_upload(upload_type=upload_type)
        ipc.send("workflow_step", step=f"publish_navigate_{upload_type}", status="done" if can_navigate else "failed")
        ipc.send(
            "action_event",
            action="publish_navigation",
            username="",
            success=can_navigate,
            data={"type": upload_type},
        )

        try:
            navigator.go_back_to_home()
        except Exception:
            pass

        return can_navigate
    except Exception as exc:
        logger.exception(f"[WorkflowTest] Publish workflow failed: {exc}")
        ipc.send("workflow_step", step=f"publish_{workflow_type}", status="error", error=str(exc))
        return False
