"""Taktik Agent IPC event helpers shared by bridge runtimes."""


class AgentIpcMixin:
    """Emit Agent events through the core IPC send primitive."""

    def agent_decision(
        self,
        action: str,
        author: str = None,
        reason: str = None,
        visit_profile: bool = False,
        comment: str = None,
        screenshot: str = None,
        cost_usd: float = None,
        model: str = None,
    ) -> None:
        """Signal a Taktik Agent feed decision."""
        data = dict(
            action=action,
            target_username=author,
            reason=reason,
            visit_profile=visit_profile,
            workflow_type="taktik_agent",
        )
        if comment:
            data["comment"] = comment
        if screenshot:
            data["screenshot"] = screenshot
        if cost_usd is not None:
            data["cost_usd"] = cost_usd
        if model:
            data["model"] = model
        self.send("agent_decision", **data)

    def agent_status(self, status: str, message: str = "", stats: dict = None) -> None:
        """Send Taktik Agent session status update."""
        data = dict(status=status, message=message, workflow_type="taktik_agent")
        if stats:
            data["stats"] = stats
        self.send("agent_status", **data)

    def strategy_switch(self, from_strategy: str, to_strategy: str, hashtag: str = None) -> None:
        """Signal that the agent is switching engagement strategy."""
        data = dict(from_strategy=from_strategy, to_strategy=to_strategy, workflow_type="taktik_agent")
        if hashtag:
            data["hashtag"] = hashtag
        self.send("strategy_switch", **data)


__all__ = ["AgentIpcMixin"]
