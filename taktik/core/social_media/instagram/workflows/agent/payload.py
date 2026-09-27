"""The one reading of a Taktik Agent payload, for the desktop bridge and the CLI.

The payload is the file the app's main process writes for the Agent node (the session's caps, the
app's language) with what the host adds (the OpenRouter key, the vision model, the orchestration
context the desktop prepared); `taktik agent run --param k=v` and `taktik workflows run
instagram.engagement.taktik_agent` send the same keys. Each key is read by a plain `.get`, here
and nowhere else: `TaktikAgentWorkflow` and its launcher take the request this module builds.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional


@dataclass(frozen=True)
class AgentOrchestration:
    """What the desktop prepared for the session (`desktop_orchestration_context`).

    The bot keeps the recent episodes and the warnings in its context, announces the intro, and
    words its planned steps with the desktop's messages when it has one for the step."""

    timeline: List[Any] = field(default_factory=list)
    pattern_warnings: List[Any] = field(default_factory=list)
    intro_message: Optional[str] = None
    next_steps: List[Any] = field(default_factory=list)
    source: str = "desktop"


@dataclass(frozen=True)
class TaktikAgentRequest:
    """What one Taktik Agent session is asked to do."""

    max_likes: Any = 80
    max_comments: Any = 15
    max_follows: Any = 20
    max_profile_visits: Any = 40
    max_posts_seen: Any = 150
    session_duration_min: Any = 25
    skip_reels: Any = True
    skip_related_profiles: Any = True
    language: Any = "en"
    vision_model: Optional[str] = None
    text_model: Optional[str] = None
    openrouter_api_key: str = ""
    agent_plan: Any = None
    orchestration: AgentOrchestration = field(default_factory=AgentOrchestration)

    @property
    def quotas(self) -> Dict[str, Any]:
        """The session's caps, by the names the payload gives them."""
        return {
            "max_likes": self.max_likes,
            "max_comments": self.max_comments,
            "max_follows": self.max_follows,
            "max_profile_visits": self.max_profile_visits,
            "max_posts_seen": self.max_posts_seen,
            "session_duration_min": self.session_duration_min,
        }


def _orchestration(context: Any) -> AgentOrchestration:
    if not isinstance(context, Mapping):
        return AgentOrchestration()
    timeline = context.get("timeline")
    warnings = context.get("patternWarnings")
    steps = context.get("nextSteps")
    return AgentOrchestration(
        timeline=timeline if isinstance(timeline, list) else [],
        pattern_warnings=warnings if isinstance(warnings, list) else [],
        intro_message=context.get("introMessage"),
        next_steps=steps if isinstance(steps, list) else [],
        source=context.get("source") or "desktop",
    )


def taktik_agent_request_from_payload(config: Mapping[str, Any]) -> TaktikAgentRequest:
    """The session a Taktik Agent payload describes.

    Without a key in the payload, the OpenRouter key is the `OPENROUTER_API_KEY` environment
    variable's, when it is set."""
    return TaktikAgentRequest(
        max_likes=config.get("max_likes", 80),
        max_comments=config.get("max_comments", 15),
        max_follows=config.get("max_follows", 20),
        max_profile_visits=config.get("max_profile_visits", 40),
        max_posts_seen=config.get("max_posts_seen", 150),
        session_duration_min=config.get("session_duration_min", 25),
        skip_reels=config.get("skip_reels", True),
        # A profile already in a relationship is skipped before its screenshot; the agent is a
        # growth path. Off only if it should one day re-engage its own audience.
        skip_related_profiles=config.get("skip_related_profiles", True),
        language=config.get("language", "en"),
        vision_model=config.get("vision_model") or None,
        text_model=config.get("text_model") or None,
        openrouter_api_key=config.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY", ""),
        agent_plan=config.get("agent_plan") or config.get("agentPlan"),
        orchestration=_orchestration(config.get("desktop_orchestration_context")),
    )


__all__ = ["AgentOrchestration", "TaktikAgentRequest", "taktik_agent_request_from_payload"]
