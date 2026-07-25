"""AI-related IPC event helpers shared by bridge runtimes."""


class AIIpcMixin:
    """Emit AI and Agent events through the core IPC send primitive."""

    def ai_profile_analyzing(self, username: str, prompt: str = None, model: str = None,
                              image_url: str = None, avatar_url: str = None,
                              prompt_key: str = None) -> None:
        """Signal that AI profile classification has started.

        `prompt` is an English fallback label; `prompt_key` (optional) is a stable i18n key the
        desktop localizes for the card's operator-facing prompt line (with @{username})."""
        data = dict(username=username, target_username=username,
                    prompt=prompt, model=model, workflow_type="automation")
        if image_url:
            data["image"] = image_url
        if avatar_url:
            data["avatar_url"] = avatar_url
        if prompt_key:
            data["prompt_key"] = prompt_key
        self.send("ai_profile_start", **data)

    def ai_profile_analyzed(self, username: str, result: str, duration_ms: int = 0,
                            model: str = None, provider: str = None, cost_usd: float = None,
                            event_id: str = None, classification: dict = None,
                            screenshot: str = None, persist_only: bool = False) -> None:
        """Signal that AI profile classification is done.

        `persist_only=True` marks a re-emit whose sole purpose is making the desktop persist
        the qualification (interaction path). The desktop's ai_profiles_analyzed counter must
        skip those, otherwise every profile is counted twice."""
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
        if persist_only:
            data["persist_only"] = True
        self.send("ai_profile_done", **data)

    def ai_screenshot_analyzing(self, username: str = None, prompt: str = None, model: str = None,
                                  image_url: str = None, prompt_key: str = None) -> None:
        """Signal that AI screenshot/post analysis has started.

        `prompt_key` (optional) is a stable i18n key the desktop localizes for the card's prompt
        line; `prompt` stays as the English fallback."""
        data = dict(target_username=username, prompt=prompt, model=model, workflow_type="automation")
        if image_url:
            data["image"] = image_url
        if prompt_key:
            data["prompt_key"] = prompt_key
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

    def ai_comment_generating(self, username: str, prompt: str = None, model: str = None,
                              prompt_key: str = None) -> None:
        """Signal that AI smart comment generation has started.

        `prompt_key` (optional) is a stable i18n key the desktop localizes for the card's prompt
        line (with @{username}); `prompt` stays as the English fallback."""
        data = dict(target_username=username, prompt=prompt, model=model, workflow_type="automation")
        if prompt_key:
            data["prompt_key"] = prompt_key
        self.send("ai_comment_start", **data)

    def ai_comment_ready(self, username: str, comment: str, duration_ms: int = 0,
                         model: str = None, provider: str = None, cost_usd: float = None,
                         reasoning: str = None, post_description: str = None,
                         post_caption: str = None, screenshot: str = None) -> None:
        """Signal that AI smart comment is ready.

        Carries the DECISION CONTEXT so the Agent card can show WHY this comment was written and
        what it reacted to: `reasoning` (the model's short why), `post_description` (the vision
        analysis of the post), `post_caption` (the author's own words), and `screenshot` (a data-URL
        thumbnail of the post that was sent to the multimodal model). Also feeds the autonomous
        mode's decision trace."""
        data = dict(target_username=username, comment=comment, result=comment,
                    duration_ms=duration_ms, model=model, provider=provider,
                    workflow_type="automation")
        if cost_usd is not None:
            data["cost_usd"] = cost_usd
        if reasoning:
            data["reasoning"] = reasoning
        if post_description:
            data["post_description"] = post_description
        if post_caption:
            data["post_caption"] = post_caption
        if screenshot:
            data["screenshot"] = screenshot
        self.send("ai_comment_done", **data)

    def ai_error(self, error: str, username: str = None) -> None:
        """Signal an AI processing error."""
        self.send("ai_error", error=error, target_username=username, workflow_type="automation")
