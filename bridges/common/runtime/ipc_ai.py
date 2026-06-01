"""AI-related IPC event helpers shared by bridge runtimes."""


class AIIpcMixin:
    """Emit AI and Agent events through the core IPC send primitive."""

    def ai_profile_analyzing(self, username: str, prompt: str = None, model: str = None,
                              image_url: str = None, avatar_url: str = None) -> None:
        """Signal that AI profile classification has started."""
        data = dict(username=username, target_username=username,
                    prompt=prompt, model=model, workflow_type="automation")
        if image_url:
            data["image"] = image_url
        if avatar_url:
            data["avatar_url"] = avatar_url
        self.send("ai_profile_start", **data)

    def ai_profile_analyzed(self, username: str, result: str, duration_ms: int = 0,
                            model: str = None, provider: str = None, cost_usd: float = None,
                            event_id: str = None, classification: dict = None,
                            screenshot: str = None) -> None:
        """Signal that AI profile classification is done."""
        data = dict(username=username, target_username=username, result=result,
                    duration_ms=duration_ms, model=model, provider=provider,
                    workflow_type="automation")
        if event_id:
            data["event_id"] = event_id
        if cost_usd is not None:
            data["cost_usd"] = cost_usd
        if classification is not None:
            data["classification"] = classification
        if screenshot is not None:
            data["screenshot"] = screenshot
        self.send("ai_profile_done", **data)

    def ai_screenshot_analyzing(self, username: str = None, prompt: str = None, model: str = None,
                                  image_url: str = None) -> None:
        """Signal that AI screenshot/post analysis has started."""
        data = dict(target_username=username, prompt=prompt, model=model, workflow_type="automation")
        if image_url:
            data["image"] = image_url
        self.send("ai_screenshot_start", **data)

    def ai_screenshot_analyzed(self, result: str, username: str = None, duration_ms: int = 0,
                               model: str = None, provider: str = None, cost_usd: float = None,
                               screenshot: str = None) -> None:
        """Signal that AI screenshot/post analysis is done."""
        data = dict(target_username=username, result=result,
                    duration_ms=duration_ms, model=model, provider=provider,
                    workflow_type="automation")
        if cost_usd is not None:
            data["cost_usd"] = cost_usd
        if screenshot is not None:
            data["screenshot"] = screenshot
        self.send("ai_screenshot_done", **data)

    def ai_comment_generating(self, username: str, prompt: str = None, model: str = None) -> None:
        """Signal that AI smart comment generation has started."""
        self.send("ai_comment_start", target_username=username,
                  prompt=prompt, model=model, workflow_type="automation")

    def ai_comment_ready(self, username: str, comment: str, duration_ms: int = 0,
                         model: str = None, provider: str = None, cost_usd: float = None) -> None:
        """Signal that AI smart comment is ready."""
        data = dict(target_username=username, comment=comment, result=comment,
                    duration_ms=duration_ms, model=model, provider=provider,
                    workflow_type="automation")
        if cost_usd is not None:
            data["cost_usd"] = cost_usd
        self.send("ai_comment_done", **data)

    def agent_decision(self, action: str, author: str = None, reason: str = None,
                       visit_profile: bool = False, comment: str = None,
                       screenshot: str = None, cost_usd: float = None,
                       model: str = None) -> None:
        """Signal a Taktik Agent feed decision."""
        data = dict(action=action, target_username=author, reason=reason,
                    visit_profile=visit_profile, workflow_type="taktik_agent")
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

    def ai_error(self, error: str, username: str = None) -> None:
        """Signal an AI processing error."""
        self.send("ai_error", error=error, target_username=username, workflow_type="automation")
