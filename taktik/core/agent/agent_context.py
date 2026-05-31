"""Runtime context for the autonomous Taktik Agent."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from taktik.core.agent.contracts import AgentPlan


@dataclass
class AgentContext:
    """Runtime context consumed by the bot during a desktop-orchestrated session."""

    platform: str = "instagram"
    account_username: str = ""
    account_id: Optional[int] = None
    persona_block: str = ""
    session_started_at: Optional[float] = None
    live_stats: Dict[str, Any] = field(default_factory=dict)
    recent_timeline: List[Dict[str, Any]] = field(default_factory=list)
    pattern_warnings: List[str] = field(default_factory=list)
    available_targets: List[Dict[str, Any]] = field(default_factory=list)
    agent_plan: Optional[AgentPlan] = None
    agent_plan_id: Optional[str] = None
    agent_plan_source: Optional[str] = None
    agent_plan_step_count: int = 0
    last_tool: Optional[str] = None
    last_error: Optional[str] = None

    def update_stats(self, stats: Dict[str, Any]) -> None:
        """Replace live stats with a shallow copy to avoid shared mutations."""
        self.live_stats = dict(stats or {})
