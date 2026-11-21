"""Threads feed runner used by the bridge dispatcher: `run_threads_feed` with IPC events."""

from bridges.common.entrypoint import send_run_error
from bridges.common.network import send_run_refusal
from bridges.threads.automation.base import send_status
from bridges.threads.automation.events import build_threads_callbacks, emit_threads_completion
from taktik.core.shared.diagnostics.run_halt import RunRefused


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
    except RunRefused as refused:
        # The launcher's door: Threads was not touched.
        send_run_refusal(refused, "Threads feed workflow")
        return False
    except Exception as exc:  # noqa: BLE001
        send_run_error(f"Threads feed workflow crashed: {exc}", exc, error_code="threads.workflow_crash")
        return False

    return bool(result["success"])
