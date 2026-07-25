"""Instagram publish workflow-test runner.

Wired to production in REHEARSAL mode: the run walks the entire publish flow — push the media,
open the creation screen, select from the gallery, advance to the composer, fill the caption —
and stops on the last screen without tapping share. Reaching the share button is the measurement;
not tapping it is what keeps a diagnostic run from posting on a real account.

It calls `InstagramPostWorkflow.execute(..., stop_before_share=True)`, the production path itself.
A bench that reimplemented the flow to avoid the final tap would be testing the bench.

`upload_reel` stays unwired: a reel needs a video, and generating a valid one without pulling in
an encoder would be a bigger lie than saying it is not ready.
"""
from __future__ import annotations

from bridges.compat.diagnostics.runtime.workflow_test.execution.not_wired import not_wired
from bridges.compat.diagnostics.runtime.workflow_test.execution.rehearsal_media import (
    discard,
    make_rehearsal_image,
)

# Bench workflow type -> production post_type. Carousel needs more than one media so the
# multi-select branch is actually exercised.
_POST_TYPES = {
    "upload_post": ("post", 1),
    "upload_carousel": ("carousel", 2),
    "upload_story": ("story", 1),
}


def run_instagram_publish(conn, device, ipc, workflow_type):
    if workflow_type == "upload_reel":
        return not_wired(
            ipc,
            workflow_type,
            "taktik.core.social_media.instagram.workflows.publish.post_workflow."
            "InstagramPostWorkflow (needs a video media, which the bench cannot generate)",
        )

    mapping = _POST_TYPES.get(workflow_type)
    if not mapping:
        ipc.send(
            "workflow_step",
            step=workflow_type,
            status="error",
            error=f"Unknown publish workflow '{workflow_type}'",
        )
        return False

    post_type, media_count = mapping

    from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
        InstagramPostWorkflow,
    )

    def _log(level, message):
        ipc.send("log", level=level, message=message)

    def _status(status, message=""):
        ipc.send("workflow_step", step=workflow_type, status=status, message=message)

    media = [make_rehearsal_image() for _ in range(media_count)]
    try:
        workflow = InstagramPostWorkflow(
            device,
            conn.device_id,
            log=_log,
            status=_status,
            post_type=post_type,
        )
        result = workflow.execute(
            caption="",
            hashtags=[],
            media_paths=media,
            stop_before_share=True,
        )
    finally:
        # The media has been pushed to the device; the local copies have served their purpose.
        for path in media:
            discard(path)

    success = bool(result.get("success"))
    ipc.send(
        "action_event",
        action="publish_rehearsal",
        username="",
        success=success,
        data={
            "workflow": workflow_type,
            "postType": post_type,
            "published": False,
            "message": result.get("message", ""),
            "errorType": result.get("error_type"),
        },
    )
    return success
