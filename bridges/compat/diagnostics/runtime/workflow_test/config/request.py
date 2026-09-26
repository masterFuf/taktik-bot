"""Config validation for compat workflow diagnostics."""

from dataclasses import dataclass
import sys

from bridges.common.runtime.entrypoint import MISSING_CONFIG

from bridges.compat.diagnostics.runtime.workflow_test.config.catalog import DEFAULT_CONFIGS, NEEDS_TARGET


@dataclass
class WorkflowTestRequest:
    device_id: str
    app_name: str
    version: str
    workflow_type: str
    target: str
    limits: dict
    probabilities: dict
    session_duration: int
    # Explicit between-actions delay window. None when the run is rhythm-driven
    # (the pacing profile from behavior_policy provides the delays instead).
    delays: dict | None
    # Profile filters mirroring the real workflow config (None = permissive defaults).
    filters: dict | None = None
    max_consecutive_known: int | None = None
    # Pacing/behaviour profile mirroring the real workflow ({"profileId": "balanced"|...}).
    behavior_policy: dict | None = None
    # Page-level workflow settings, in the desktop bridge's camelCase vocabulary
    # (`engagePosts`, `walkLikers`, `feed: {...}`, …). Passed verbatim to the production
    # config builder, which owns their whitelist — so a setting added to a workflow page
    # reaches the bench without a single change in this bridge.
    options: dict | None = None


def report_workflow_test_entry_error(ipc):
    """Entry failures (no file, unreadable file) as the Lab's error events."""

    def report(message: str, reason: str) -> None:
        code = "MISSING_CONFIG" if reason == MISSING_CONFIG else "CONFIG_ERROR"
        ipc.send("error", error=message, error_code=code)

    return report


def load_workflow_test_request(ipc, config: dict) -> WorkflowTestRequest:
    """Validate a workflow-test config and emit legacy IPC errors on failure."""
    device_id = config.get("device_id", "")
    app_name = config.get("app", "instagram")
    version = config.get("version", "")
    workflow_type = config.get("workflow", "target_followers")
    target = config.get("target", "")

    if not device_id:
        ipc.send("error", error="No device_id provided", error_code="MISSING_DEVICE")
        sys.exit(1)

    if not target and workflow_type in NEEDS_TARGET:
        ipc.send("error", error="No target provided for this workflow", error_code="MISSING_TARGET")
        sys.exit(1)

    defaults = DEFAULT_CONFIGS.get(
        workflow_type,
        DEFAULT_CONFIGS.get("target_followers", {"limits": {}, "probabilities": {}}),
    )
    limits = {**defaults.get("limits", {}), **config.get("limits", {})}
    probabilities = {**defaults.get("probabilities", {}), **config.get("probabilities", {})}

    return WorkflowTestRequest(
        device_id=device_id,
        app_name=app_name,
        version=version,
        workflow_type=workflow_type,
        target=target,
        limits=limits,
        probabilities=probabilities,
        session_duration=config.get("session_duration", 30),
        # Absent delays => rhythm-driven; the automation builder omits the explicit
        # delay window so the pacing profile takes over.
        delays=config.get("delays"),
        filters=config.get("filters") or None,
        max_consecutive_known=config.get("maxConsecutiveKnownUsernames"),
        behavior_policy=config.get("behaviorPolicy") or None,
        options=config.get("options") or None,
    )


__all__ = ["WorkflowTestRequest", "load_workflow_test_request", "report_workflow_test_entry_error"]
