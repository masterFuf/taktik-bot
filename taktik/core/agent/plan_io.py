"""JSON-safe AgentPlan parsing and serialization."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Optional

from taktik.core.agent.contracts import AgentPlan, PlanStep, WorkflowInvocation
from taktik.core.agent.workflow_manifest import WorkflowManifest


def agent_plan_from_payload(
    payload: Mapping[str, Any],
    manifest: Optional[WorkflowManifest] = None,
) -> AgentPlan:
    """Build an AgentPlan from a JSON-like payload."""
    if not isinstance(payload, Mapping):
        raise ValueError("Agent plan payload must be an object")

    plan_id = _required_string(payload, "plan_id")
    steps_payload = payload.get("steps") or []
    if not isinstance(steps_payload, list):
        raise ValueError("Agent plan steps must be a list")

    steps = [_plan_step_from_payload(item, manifest=manifest) for item in steps_payload]
    return AgentPlan(
        plan_id=plan_id,
        source=str(payload.get("source") or "standalone"),
        platform=str(payload.get("platform") or "multi"),
        steps=steps,
        variables=_object_payload(payload.get("variables"), "variables"),
        metadata=_object_payload(payload.get("metadata"), "metadata"),
    )


def agent_plan_to_payload(plan: AgentPlan) -> dict[str, Any]:
    """Serialize an AgentPlan into a JSON-safe dict."""
    return asdict(plan)


def _plan_step_from_payload(
    payload: Mapping[str, Any],
    manifest: Optional[WorkflowManifest] = None,
) -> PlanStep:
    if not isinstance(payload, Mapping):
        raise ValueError("Agent plan step must be an object")

    workflow_payload = payload.get("workflow")
    workflow = None
    if workflow_payload is not None:
        workflow = _workflow_invocation_from_payload(workflow_payload, manifest=manifest)

    conditions = payload.get("conditions") or []
    if not isinstance(conditions, list):
        raise ValueError("Agent plan step conditions must be a list")

    return PlanStep(
        step_id=_required_string(payload, "step_id"),
        kind=str(payload.get("kind") or "workflow"),
        workflow=workflow,
        conditions=[str(item) for item in conditions],
        metadata=_object_payload(payload.get("metadata"), "metadata"),
    )


def _workflow_invocation_from_payload(
    payload: Mapping[str, Any],
    manifest: Optional[WorkflowManifest] = None,
) -> WorkflowInvocation:
    if not isinstance(payload, Mapping):
        raise ValueError("Agent workflow invocation must be an object")

    platform = _required_string(payload, "platform")
    workflow_id = _required_string(payload, "workflow_id")
    if manifest is not None and not manifest.contains(workflow_id):
        raise ValueError(f"Unknown workflow_id: {workflow_id}")

    return WorkflowInvocation(
        platform=platform,
        workflow_id=workflow_id,
        params=_object_payload(payload.get("params"), "params"),
    )


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Agent plan field '{key}' must be a non-empty string")
    return value


def _object_payload(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"Agent plan field '{key}' must be an object")
    return dict(value)
