"""Honest failure for a bench workflow that is not wired to production yet.

The scraping / DM / publish runners of this bench were written against modules that have never
existed in this repository — verified against the full git history, not merely against the
current tree. They were not broken by a refactor: they were aspirational from the first commit,
so every run of those workflows raised ImportError the moment it was invoked, behind a generic
`except Exception` that reported it as an ordinary workflow failure.

A bench that lies about why it failed is worse than one that says it is not ready. This makes
the gap explicit and carries the address of the production entry point the runner has to be
wired to, so the work is described where it has to be done.

Wiring one of these is NOT a mechanical import swap. The production entry points do not share
one shape: `InstagramPostWorkflow` takes an already-connected device, the DM logic lives in the
bridge runtime and owns its own connection, and the scraping runner is CLI-shaped (argv). Each
needs a decision about who owns the device and the IPC, then validation on a real phone.
"""
from __future__ import annotations

from loguru import logger


def not_wired(ipc, workflow_type: str, production_entry_point: str) -> bool:
    """Report `workflow_type` as unavailable, naming what it must call. Always False."""
    message = (
        f"Workflow '{workflow_type}' is not wired to production. "
        f"It must call {production_entry_point}, which needs an owner for the device and the "
        f"IPC channel, then validation on a device."
    )
    logger.warning(f"[WorkflowTest] {message}")
    ipc.send("workflow_step", step=workflow_type, status="error", error=message)
    ipc.send(
        "action_event",
        action="workflow_not_wired",
        username="",
        success=False,
        data={"workflow": workflow_type, "productionEntryPoint": production_entry_point},
    )
    return False


__all__ = ["not_wired"]
