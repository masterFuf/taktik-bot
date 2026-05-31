"""Contracts for the Taktik Agent runtime kernel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class WorkflowInvocation:
    """Executable workflow reference resolved by the agent kernel."""

    platform: str
    workflow_id: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanStep:
    """Single execution step inside an agent plan."""

    step_id: str
    kind: str = "workflow"
    workflow: Optional[WorkflowInvocation] = None
    conditions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentPlan:
    """Portable execution plan prepared by the desktop app or by Python."""

    plan_id: str
    source: str = "standalone"
    platform: str = "multi"
    steps: List[PlanStep] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentEvent:
    """Structured runtime event emitted by the agent kernel."""

    event_type: str
    status: str
    step_id: Optional[str] = None
    workflow_id: Optional[str] = None
    message: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
