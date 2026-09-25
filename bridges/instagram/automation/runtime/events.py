"""Bridge event emitters for Instagram desktop automation runtime."""

from __future__ import annotations

import json
import traceback

from bridges.instagram.runtime.ipc import send_error, send_log, send_message, send_stats, send_status

#: Tail of the traceback attached to a workflow error. The cause is at the end.
MAX_TRACEBACK_CHARS = 8000


def send_instagram_session_config(config: dict, *, ai_enabled: bool) -> None:
    from taktik.core.social_media.instagram.workflows.core.config_builder import (
        build_instagram_session_config_event,
    )

    send_message(
        "session_config",
        config=build_instagram_session_config_event(
            config,
            ai_enabled=ai_enabled,
        ),
    )


def send_instagram_workflow_final_stats(stats: dict) -> None:
    send_stats(
        likes=stats.get("likes", 0),
        follows=stats.get("follows", 0),
        comments=stats.get("comments", 0),
        profiles=stats.get("interactions", 0),
        unfollows=stats.get("unfollows", 0),
    )


def send_instagram_workflow_error(error: Exception) -> None:
    """Report a workflow failure, with the traceback that explains it.

    The classification stays a substring match on the message — the exceptions raised down there
    are plain `Exception`s and carry no code — but the traceback now travels with the event, so a
    crash report no longer arrives as one sentence with no frame to look at.
    """
    error_msg = str(error)
    tb = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )[-MAX_TRACEBACK_CHARS:]

    if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
        send_error(
            f"UIAutomator2 crashed during workflow: {error_msg}",
            error_code="ATX_AGENT_CRASHED",
            traceback=tb,
        )
    elif "timeout" in error_msg.lower():
        send_error(
            f"Workflow timed out: {error_msg}",
            error_code="WORKFLOW_TIMEOUT",
            traceback=tb,
        )
    else:
        send_error(
            f"Workflow error: {error_msg}",
            error_code="WORKFLOW_ERROR",
            traceback=tb,
        )


class InstagramAutomationReporter:
    """What the desktop sees of a run, at the moments the core launcher reports.

    `run_instagram_automation` calls it when the workflow config is built, when the run starts
    and when it ends; the events are the ones the bridge printed before the run moved to the core.
    """

    def __init__(self, config: dict, *, ai_enabled: bool):
        self.config = config
        self.ai_enabled = ai_enabled

    def config_built(self, workflow_config: dict) -> None:
        target = self.config.get("target", "")
        workflow_type = self.config.get("workflowType")
        targets_display = ", @".join([t.strip() for t in target.split(",") if t.strip()])
        send_status("starting", f"Starting {workflow_type} workflow for @{targets_display}")
        send_log("info", f"Configuration: {json.dumps(workflow_config, indent=2)}")
        send_instagram_session_config(self.config, ai_enabled=self.ai_enabled)
        send_status("initializing", "Initializing automation...")

    def running(self) -> None:
        send_status("running", "Running workflow...")

    def finished(self, stats: dict) -> None:
        send_instagram_workflow_final_stats(stats)
        send_status("completed", "Workflow completed successfully")
