"""Minimal plan executor for the Taktik Agent runtime kernel."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from taktik.core.agent.kernel.contracts import AgentEvent, AgentPlan, PlanStep
from taktik.core.agent.kernel.registry import WorkflowRegistry


class AgentPlanExecutor:
    """Execute a resolved plan step by step through the workflow registry."""

    def __init__(
        self,
        registry: WorkflowRegistry,
        event_sink: Optional[Callable[[AgentEvent], None]] = None,
    ) -> None:
        self.registry = registry
        self.event_sink = event_sink

    def execute(self, plan: AgentPlan) -> List[AgentEvent]:
        events: List[AgentEvent] = []

        for step in plan.steps:
            if step.kind != "workflow" or step.workflow is None:
                events.append(self._emit("skipped", step, message="Unsupported or empty plan step"))
                continue

            events.append(self._emit("started", step, workflow_id=step.workflow.workflow_id))

            handler = self.registry.resolve(step.workflow.workflow_id)
            payload = dict(plan.variables)
            payload.update(step.workflow.params)
            payload["_plan_id"] = plan.plan_id
            payload["_step_id"] = step.step_id

            try:
                result = handler(step.workflow, payload)
            except Exception as exc:
                events.append(
                    self._emit(
                        "failed",
                        step,
                        workflow_id=step.workflow.workflow_id,
                        message=str(exc),
                    )
                )
                raise

            events.append(
                self._emit(
                    "completed",
                    step,
                    workflow_id=step.workflow.workflow_id,
                    payload=result or {},
                )
            )

        return events

    def _emit(
        self,
        status: str,
        step: PlanStep,
        workflow_id: Optional[str] = None,
        message: str = "",
        payload: Optional[Dict[str, object]] = None,
    ) -> AgentEvent:
        event = AgentEvent(
            event_type="plan_step",
            status=status,
            step_id=step.step_id,
            workflow_id=workflow_id,
            message=message,
            payload=dict(payload or {}),
        )
        if self.event_sink is not None:
            self.event_sink(event)
        return event
