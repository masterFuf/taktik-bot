"""Config loading and validation for compat workflow diagnostics."""

from dataclasses import dataclass
import json
import sys

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


def load_workflow_test_request(ipc, argv: list[str]) -> WorkflowTestRequest:
    """Load a workflow-test config file and emit legacy IPC errors on failure."""
    if len(argv) < 2:
        ipc.send("error", error="No config file provided", error_code="MISSING_CONFIG")
        sys.exit(1)

    config_path = argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as file_obj:
            config = json.load(file_obj)
    except Exception as exc:
        ipc.send("error", error=f"Failed to read config: {exc}", error_code="CONFIG_ERROR")
        sys.exit(1)

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
    )


__all__ = ["WorkflowTestRequest", "load_workflow_test_request"]
