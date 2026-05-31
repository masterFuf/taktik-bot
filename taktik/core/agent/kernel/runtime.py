"""Facade for parsing and executing agent plans with injected handlers."""

from __future__ import annotations

from typing import Any, Callable, List, Mapping, Optional

from taktik.core.agent.io.manifest import WorkflowManifest, load_workflow_manifest
from taktik.core.agent.io.plan import agent_plan_from_payload
from taktik.core.agent.kernel.contracts import AgentEvent, AgentPlan
from taktik.core.agent.kernel.executor import AgentPlanExecutor
from taktik.core.agent.kernel.registry import WorkflowRegistry


class AgentRuntime:
    """Small runtime boundary for Front/CLI supplied agent plans.

    The runtime owns parsing and execution orchestration, while concrete
    workflow handlers are still injected by a bridge or standalone caller.
    """

    def __init__(
        self,
        registry: Optional[WorkflowRegistry] = None,
        manifest: Optional[WorkflowManifest] = None,
        event_sink: Optional[Callable[[AgentEvent], None]] = None,
        validate_manifest: bool = True,
    ) -> None:
        self.registry = registry or WorkflowRegistry()
        self.manifest = manifest if manifest is not None else (
            load_workflow_manifest() if validate_manifest else None
        )
        self.event_sink = event_sink

    def plan_from_payload(self, payload: Mapping[str, Any]) -> AgentPlan:
        """Parse a JSON-like payload into an AgentPlan."""
        return agent_plan_from_payload(payload, manifest=self.manifest)

    def missing_workflow_handlers(self, plan: AgentPlan) -> tuple[str, ...]:
        """Return workflow ids that are valid but not registered for execution."""
        return self.registry.missing_for_plan(plan)

    def execute_plan(self, plan: AgentPlan) -> List[AgentEvent]:
        """Execute an already parsed plan through the injected registry."""
        executor = AgentPlanExecutor(self.registry, event_sink=self.event_sink)
        return executor.execute(plan)

    def execute_payload(self, payload: Mapping[str, Any]) -> List[AgentEvent]:
        """Parse and execute a JSON-like plan payload."""
        return self.execute_plan(self.plan_from_payload(payload))
