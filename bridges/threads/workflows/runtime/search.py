"""Threads search runner used by the bridge dispatcher: `run_threads_search` with IPC events."""

from bridges.threads.base import logger, send_error, send_status
from bridges.threads.workflows.runtime.events import build_threads_callbacks, emit_threads_completion


def run_follow(config: dict) -> bool:
    """Threads Search-and-Interact workflow (follow, target), through its launcher."""
    from taktik.core.social_media.threads.workflows.agent_handler import (
        ThreadsSearchQueryMissing,
        run_threads_search,
    )

    try:
        result = run_threads_search(
            config,
            **build_threads_callbacks(),
            on_started=lambda cfg: send_status("running", f"Threads search workflow on {cfg.device_id}"),
            on_finished=lambda stats: emit_threads_completion("Threads search workflow", stats),
        )
    except ThreadsSearchQueryMissing:
        send_error("No search query provided", error_code="threads.no_query")
        return False
    except Exception as exc:  # noqa: BLE001
        send_error(f"Threads search workflow crashed: {exc}", error_code="threads.workflow_crash")
        logger.exception("Threads search workflow crashed")
        return False

    return bool(result["success"])
