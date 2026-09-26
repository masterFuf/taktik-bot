"""Threads feed runner used by the bridge dispatcher: `run_threads_feed` with IPC events."""

from bridges.threads.base import logger, send_error, send_status
from bridges.threads.workflows.runtime.events import build_threads_callbacks, emit_threads_completion


def run_feed(config: dict) -> bool:
    """Threads Feed & Interact workflow, through its launcher."""
    from taktik.core.social_media.threads.workflows.agent_handler import run_threads_feed

    try:
        result = run_threads_feed(
            config,
            **build_threads_callbacks(),
            on_started=lambda cfg: send_status("running", f"Threads feed workflow on {cfg.device_id}"),
            on_finished=lambda stats: emit_threads_completion("Threads feed workflow", stats),
        )
    except Exception as exc:  # noqa: BLE001
        send_error(f"Threads feed workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads feed workflow crashed")
        return False

    return bool(result["success"])
